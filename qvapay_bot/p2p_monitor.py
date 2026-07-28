from __future__ import annotations

import asyncio
import logging
import random
from collections import deque
from typing import Any

from qvapay_bot.notifier import EventType, MonitorEvent, MonitorNotifier
from qvapay_bot.p2p_filters import (
    build_offer_snapshot,
    evaluate_offer,
    sort_eligible_offers,
    summarize_discarded_reasons,
)
from qvapay_bot.p2p_models import (
    MAX_HISTORY_ITEMS,
    MIN_P2P_POLL_INTERVAL_SECONDS,
    OfferEvaluation,
    OfferHistoryEntry,
    OfferProcessResult,
    P2PMonitorChatState,
    P2PMonitorCycleReport,
    P2POfferSnapshot,
    P2POfferType,
    offer_history_from_offer,
    to_optional_float,
    trim_history,
    utcnow_iso,
)
from qvapay_bot.p2p_repository import P2PMonitorStateStore
from qvapay_bot.qvapay_client import COMMAND_INDEX, QvaPayClient
from qvapay_bot.serialization import (
    cycle_report_to_dict,
    history_entry_to_dict,
    offer_snapshot_to_dict,
)
from qvapay_bot.state import BotStateStore, ChatAuthState

LOGGER = logging.getLogger(__name__)
ERROR_NOTIFICATION_COOLDOWN_SECONDS = 300.0


def _task_key(user_id: str, monitor_id: str) -> str:
    return f"{user_id}::{monitor_id}"


class P2PMonitorManager:
    """Orquesta el monitoreo P2P por monitor.

    Cada monitor habilitado (un usuario puede tener varios) corre en su propia tarea
    asyncio (`_monitor_loop`). Los efectos hacia la UI se emiten como `MonitorEvent`s
    a través del `MonitorNotifier` inyectado; cada evento lleva `monitor_id`/`monitor_name`
    para que el frontend pueda enrutarlos. El stream SSE sigue siendo por usuario.
    """

    def __init__(
        self,
        *,
        state_store: BotStateStore,
        repository: P2PMonitorStateStore,
        qvapay_client: QvaPayClient,
        notifier: MonitorNotifier,
    ) -> None:
        self._state_store = state_store
        self._repository = repository
        self._qvapay_client = qvapay_client
        self._notifier = notifier
        self._recent_apply_attempts: deque[float] = deque()
        self._apply_lock = asyncio.Lock()
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._last_error_notification_at: dict[tuple[str, str], float] = {}

    # -- Lifecycle -----------------------------------------------------------

    async def restore_tasks(self) -> None:
        restored = 0
        for user_id, monitor in self._repository.iter_all_enabled():
            auth_state = self._state_store.get_chat_state(user_id)
            if auth_state.has_bearer:
                self._start_monitor_task(user_id, monitor.id)
                restored += 1
        LOGGER.info("P2P monitor tasks restored count=%s", restored)

    async def restart_monitor(self, user_id: str, monitor_id: str) -> None:
        await self.stop_monitor(user_id, monitor_id)
        monitor = self._repository.get_monitor(user_id, monitor_id)
        auth_state = self._state_store.get_chat_state(user_id)
        if monitor is not None and monitor.enabled and auth_state.has_bearer:
            LOGGER.info(
                "Starting P2P monitor task user_id=%s monitor_id=%s interval=%s",
                user_id,
                monitor_id,
                monitor.poll_interval_seconds,
            )
            self._start_monitor_task(user_id, monitor_id)
        else:
            LOGGER.info(
                "P2P monitor task not started user_id=%s monitor_id=%s enabled=%s has_bearer=%s",
                user_id,
                monitor_id,
                monitor.enabled if monitor else None,
                auth_state.has_bearer,
            )

    async def stop_monitor(self, user_id: str, monitor_id: str) -> None:
        task = self._tasks.pop(_task_key(user_id, monitor_id), None)
        if task is not None:
            task.cancel()
            LOGGER.info(
                "Stopped P2P monitor task user_id=%s monitor_id=%s", user_id, monitor_id
            )

    async def shutdown(self) -> None:
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        self._tasks.clear()

    def is_running(self, user_id: str, monitor_id: str) -> bool:
        task = self._tasks.get(_task_key(user_id, monitor_id))
        return task is not None and not task.done()

    # -- Scheduler -----------------------------------------------------------

    def _start_monitor_task(self, user_id: str, monitor_id: str) -> None:
        key = _task_key(user_id, monitor_id)
        existing = self._tasks.pop(key, None)
        if existing is not None:
            existing.cancel()
        self._tasks[key] = asyncio.create_task(
            self._monitor_loop(user_id, monitor_id),
            name=f"p2p_monitor_{key}",
        )

    async def _monitor_loop(self, user_id: str, monitor_id: str) -> None:
        key = _task_key(user_id, monitor_id)
        try:
            while True:
                monitor = self._repository.get_monitor(user_id, monitor_id)
                auth_state = self._state_store.get_chat_state(user_id)
                if monitor is None or not monitor.enabled or not auth_state.has_bearer:
                    break

                try:
                    report = await self.run_cycle_once(
                        user_id, monitor_id, auth_state, force=False
                    )
                    await self._emit(
                        user_id,
                        monitor,
                        EventType.CYCLE_COMPLETED,
                        cycle_report_to_dict(report),
                    )
                    if report.error_message and self._should_notify_error(
                        key, report.error_message
                    ):
                        await self._emit(
                            user_id,
                            monitor,
                            EventType.ERROR,
                            {"message": report.error_message},
                        )
                except Exception as exc:  # noqa: BLE001
                    error_message = f"Unhandled P2P monitor error: {exc}"
                    LOGGER.exception(
                        "Unhandled exception in P2P monitor loop user_id=%s monitor_id=%s",
                        user_id,
                        monitor_id,
                    )
                    self._set_error(user_id, monitor, error_message)
                    if self._should_notify_error(key, error_message):
                        await self._emit(
                            user_id, monitor, EventType.ERROR, {"message": error_message}
                        )

                sleep_seconds = max(
                    monitor.poll_interval_seconds, MIN_P2P_POLL_INTERVAL_SECONDS
                )
                await asyncio.sleep(sleep_seconds)
        except asyncio.CancelledError:
            LOGGER.info(
                "P2P monitor loop cancelled user_id=%s monitor_id=%s",
                user_id,
                monitor_id,
            )
            raise
        finally:
            if self._tasks.get(key) is asyncio.current_task():
                self._tasks.pop(key, None)

    # -- Cycle ---------------------------------------------------------------

    async def run_cycle_once(
        self,
        user_id: str,
        monitor_id: str,
        auth_state: ChatAuthState,
        *,
        force: bool,
        dry_run: bool = False,
    ) -> P2PMonitorCycleReport:
        report = P2PMonitorCycleReport()
        monitor = self._repository.get_monitor(user_id, monitor_id)
        if monitor is None:
            report.error_message = "Monitor not found."
            return report
        report.applied_rules = monitor.rules
        if not force and not monitor.enabled:
            report.error_message = "P2P monitor is disabled."
            return report
        if not auth_state.has_bearer:
            error_message = "A bearer token is required to monitor P2P offers."
            self._set_error(user_id, monitor, error_message)
            report.error_message = error_message
            return report

        LOGGER.info(
            "Starting P2P monitor cycle user_id=%s monitor_id=%s force=%s dry_run=%s target_type=%s coin=%s",
            user_id,
            monitor_id,
            force,
            dry_run,
            monitor.target_type.value,
            monitor.rules.coin or "any",
        )
        await self._emit(user_id, monitor, EventType.CYCLE_STARTED, {"dry_run": dry_run})

        await self._ensure_user_profile(user_id, auth_state)
        response = await self._qvapay_client.execute(
            COMMAND_INDEX["list_p2p"],
            self._build_list_arguments(monitor),
            auth_state,
        )
        if response.status_code == 429:
            report.rate_limited = True
            report.error_message = "QvaPay rate limit reached while reading P2P offers."
            report.next_sleep_seconds = self._build_backoff_seconds(monitor)
            self._set_error(user_id, monitor, report.error_message)
            return report
        if response.status_code in (401, 403):
            report.error_message = (
                "Sesión de QvaPay expirada o sin permiso. Cierra sesión y vuelve a "
                "iniciar sesión para renovar el acceso."
            )
            self._set_error(user_id, monitor, report.error_message)
            return report
        if response.status_code >= 400:
            report.error_message = (
                f"Unable to read P2P offers. HTTP {response.status_code}."
            )
            self._set_error(user_id, monitor, report.error_message)
            return report

        offers_raw = None
        if isinstance(response.body, dict):
            offers_raw = response.body.get("data") or response.body.get("offers")
        if not isinstance(offers_raw, list):
            LOGGER.error(
                "Invalid /p2p payload user_id=%s monitor_id=%s status_code=%s body=%r",
                user_id,
                monitor_id,
                response.status_code,
                response.body,
            )
            report.error_message = "QvaPay returned an invalid payload for /p2p."
            self._set_error(user_id, monitor, report.error_message)
            return report

        offers = [
            offer
            for item in offers_raw
            if (offer := build_offer_snapshot(item)) is not None
        ]
        evaluations = [
            evaluate_offer(
                offer,
                monitor.rules,
                target_type=monitor.target_type,
                current_user_uuid=auth_state.user_uuid,
                processed_offer_timestamps=monitor.processed_offer_timestamps,
            )
            for offer in offers
        ]
        report.read_count = len(offers)
        report.filtered_count = sum(
            1 for evaluation in evaluations if evaluation.is_eligible
        )
        report.discarded_count = len(evaluations) - report.filtered_count
        report.top_discarded_reasons = summarize_discarded_reasons(evaluations)

        LOGGER.info(
            "Fetched P2P offers user_id=%s monitor_id=%s read=%s eligible=%s discarded=%s top_discarded=%s",
            user_id,
            monitor_id,
            report.read_count,
            report.filtered_count,
            report.discarded_count,
            ", ".join(report.top_discarded_reasons) or "none",
        )

        evaluated_at = utcnow_iso()
        self._remember_cycle_entries(monitor, evaluations, evaluated_at)

        sorted_candidates = sort_eligible_offers(evaluations, monitor.rules)

        if monitor.target_type == P2POfferType.BUY and sorted_candidates:
            balance = await self.fetch_balance(auth_state)
            if balance is not None:
                if balance < 1:
                    LOGGER.info(
                        "Balance too low to buy user_id=%s monitor_id=%s balance=%.2f, stopping monitor",
                        user_id,
                        monitor_id,
                        balance,
                    )
                    monitor.enabled = False
                    self._repository.save_monitor(user_id, monitor)
                    await self._emit(
                        user_id, monitor, EventType.BALANCE_LOW, {"balance": balance}
                    )
                    await self._emit(
                        user_id,
                        monitor,
                        EventType.MONITOR_STOPPED,
                        {"reason": "balance_low", "balance": balance},
                    )
                    report.error_message = "Balance too low."
                    return report
                sorted_candidates = [
                    o for o in sorted_candidates if o.amount <= balance
                ]

        if not sorted_candidates:
            LOGGER.info(
                "No eligible P2P offers found user_id=%s monitor_id=%s",
                user_id,
                monitor_id,
            )
            monitor.last_error = None
            monitor.last_error_at = None
            monitor.last_success_at = evaluated_at
            self._repository.save_monitor(user_id, monitor)
            return report

        selected_offer = sorted_candidates[0]
        report.selected_offer = selected_offer
        LOGGER.info(
            "Selected P2P offer user_id=%s monitor_id=%s uuid=%s ratio=%.6f amount=%.2f coin=%s",
            user_id,
            monitor_id,
            selected_offer.uuid,
            selected_offer.ratio,
            selected_offer.amount,
            selected_offer.coin,
        )
        await self._emit(
            user_id,
            monitor,
            EventType.OFFER_SELECTED,
            {"offer": offer_snapshot_to_dict(selected_offer), "dry_run": dry_run},
        )

        first_detected_at = self._remember_first_seen(
            monitor, selected_offer.uuid, evaluated_at
        )
        matched_entry = offer_history_from_offer(
            selected_offer,
            evaluated_at=evaluated_at,
            first_detected_at=first_detected_at,
            result=OfferProcessResult.MATCHED,
        )
        report.matched_entry = matched_entry
        monitor.notified_history = trim_history(
            [matched_entry, *monitor.notified_history]
        )

        if dry_run:
            monitor.last_error = None
            monitor.last_error_at = None
            monitor.last_success_at = evaluated_at
            self._repository.save_monitor(user_id, monitor)
            return report

        final_entry = await self._attempt_apply(
            user_id,
            monitor,
            auth_state,
            selected_offer,
            evaluated_at,
            first_detected_at,
        )
        report.final_entry = final_entry
        monitor.last_error = None
        monitor.last_error_at = None
        monitor.last_success_at = evaluated_at
        self._repository.save_monitor(user_id, monitor)

        await self._emit(
            user_id,
            monitor,
            EventType.APPLY_RESULT,
            {"entry": history_entry_to_dict(final_entry)},
        )

        if (
            monitor.target_type == P2POfferType.BUY
            and final_entry.result == OfferProcessResult.APPLIED
        ):
            post_balance = await self.fetch_balance(auth_state)
            if post_balance is not None and post_balance < 1:
                monitor.enabled = False
                self._repository.save_monitor(user_id, monitor)
                await self._emit(
                    user_id, monitor, EventType.BALANCE_LOW, {"balance": post_balance}
                )
                await self._emit(
                    user_id,
                    monitor,
                    EventType.MONITOR_STOPPED,
                    {"reason": "balance_low", "balance": post_balance},
                )

        return report

    async def _attempt_apply(
        self,
        user_id: str,
        monitor: P2PMonitorChatState,
        auth_state: ChatAuthState,
        offer: P2POfferSnapshot,
        evaluated_at: str,
        first_detected_at: str,
    ) -> OfferHistoryEntry:
        applied_at = utcnow_iso()
        async with self._apply_lock:
            self._prune_apply_window()
            if len(self._recent_apply_attempts) >= 2:
                LOGGER.info(
                    "Skipping P2P apply due to local throttle user_id=%s monitor_id=%s uuid=%s",
                    user_id,
                    monitor.id,
                    offer.uuid,
                )
                entry = offer_history_from_offer(
                    offer,
                    evaluated_at=evaluated_at,
                    first_detected_at=first_detected_at,
                    applied_at=applied_at,
                    result=OfferProcessResult.RATE_LIMITED,
                    reason="Local apply throttle active.",
                )
                monitor.processed_offer_timestamps[offer.uuid] = applied_at
                monitor.applied_history = trim_history(
                    [entry, *monitor.applied_history]
                )
                return entry
            self._recent_apply_attempts.append(asyncio.get_running_loop().time())

        LOGGER.info(
            "Attempting to apply P2P offer user_id=%s monitor_id=%s uuid=%s ratio=%.6f amount=%.2f coin=%s",
            user_id,
            monitor.id,
            offer.uuid,
            offer.ratio,
            offer.amount,
            offer.coin,
        )

        response = await self._qvapay_client.execute(
            COMMAND_INDEX["apply_p2p"],
            {"uuid": offer.uuid},
            auth_state,
        )
        if response.status_code == 201:
            result = OfferProcessResult.APPLIED
            reason = "Offer applied successfully."
            target_history = "applied"
        elif response.status_code == 409:
            result = OfferProcessResult.LOST_RACE
            reason = "Offer was taken by another peer first."
            target_history = "lost_race"
        elif response.status_code == 429:
            result = OfferProcessResult.RATE_LIMITED
            reason = "QvaPay rate limited the apply request."
            target_history = "applied"
        elif response.status_code in {400, 403}:
            result = OfferProcessResult.REJECTED
            reason = (
                _extract_error_message(response.body) or f"HTTP {response.status_code}"
            )
            target_history = "applied"
        else:
            result = OfferProcessResult.ERROR
            reason = (
                _extract_error_message(response.body) or f"HTTP {response.status_code}"
            )
            target_history = "applied"

        LOGGER.info(
            "P2P apply result user_id=%s monitor_id=%s uuid=%s status_code=%s result=%s reason=%s",
            user_id,
            monitor.id,
            offer.uuid,
            response.status_code,
            result.value,
            reason,
        )

        entry = offer_history_from_offer(
            offer,
            evaluated_at=evaluated_at,
            first_detected_at=first_detected_at,
            applied_at=applied_at,
            result=result,
            reason=reason,
        )
        monitor.processed_offer_timestamps[offer.uuid] = applied_at
        monitor.seen_offer_ids = [
            offer.uuid,
            *[item for item in monitor.seen_offer_ids if item != offer.uuid],
        ][:100]
        if target_history == "lost_race":
            monitor.lost_race_history = trim_history(
                [entry, *monitor.lost_race_history]
            )
        else:
            monitor.applied_history = trim_history([entry, *monitor.applied_history])
        return entry

    # -- QvaPay helpers ------------------------------------------------------

    async def _ensure_user_profile(
        self, user_id: str, auth_state: ChatAuthState
    ) -> None:
        if auth_state.user_uuid:
            return

        response = await self._qvapay_client.execute(
            COMMAND_INDEX["profile"],
            {},
            auth_state,
        )
        if not isinstance(response.body, dict) or response.status_code >= 400:
            return

        user_uuid = response.body.get("uuid")
        username = response.body.get("username")
        if isinstance(user_uuid, str) and user_uuid.strip():
            auth_state.user_uuid = user_uuid.strip()
        if isinstance(username, str) and username.strip():
            auth_state.username = username.strip()
        auth_state.kyc = bool(response.body.get("kyc", False))
        auth_state.p2p_enabled = bool(response.body.get("p2p_enabled", False))
        self._state_store.save_chat_state(user_id, auth_state)

    async def fetch_balance(self, auth_state: ChatAuthState) -> float | None:
        if not auth_state.has_bearer:
            return None
        response = await self._qvapay_client.execute(
            COMMAND_INDEX["profile"],
            {},
            auth_state,
        )
        if response.status_code == 200 and isinstance(response.body, dict):
            return to_optional_float(response.body.get("balance"))
        return None

    def _build_list_arguments(self, monitor: P2PMonitorChatState) -> dict[str, Any]:
        arguments: dict[str, Any] = {
            "page": 1,
            "take": 100,
            "status": "open",
        }
        if monitor.target_type != P2POfferType.ANY:
            arguments["type"] = monitor.target_type.value
        if monitor.rules.coin:
            arguments["coin"] = monitor.rules.coin
        return arguments

    # -- State bookkeeping ---------------------------------------------------

    def _remember_cycle_entries(
        self,
        monitor: P2PMonitorChatState,
        evaluations: list[OfferEvaluation],
        evaluated_at: str,
    ) -> None:
        filtered_entries = []
        discarded_entries = []
        for evaluation in evaluations[:MAX_HISTORY_ITEMS]:
            first_detected_at = self._remember_first_seen(
                monitor, evaluation.offer.uuid, evaluated_at
            )
            entry = offer_history_from_offer(
                evaluation.offer,
                evaluated_at=evaluated_at,
                first_detected_at=first_detected_at,
                result=OfferProcessResult.MATCHED if evaluation.is_eligible else None,
                reason=", ".join(evaluation.reasons) if evaluation.reasons else None,
            )
            if evaluation.is_eligible:
                filtered_entries.append(entry)
            else:
                discarded_entries.append(entry)

        monitor.filtered_history = trim_history(
            filtered_entries + monitor.filtered_history
        )
        monitor.discarded_history = trim_history(
            discarded_entries + monitor.discarded_history
        )

    def _remember_first_seen(
        self,
        monitor: P2PMonitorChatState,
        offer_uuid: str,
        detected_at: str,
    ) -> str:
        if offer_uuid not in monitor.first_seen_at_by_offer:
            monitor.first_seen_at_by_offer[offer_uuid] = detected_at
        return monitor.first_seen_at_by_offer[offer_uuid]

    def _set_error(
        self,
        user_id: str,
        monitor: P2PMonitorChatState,
        error_message: str,
    ) -> None:
        LOGGER.error(
            "P2P monitor error user_id=%s monitor_id=%s message=%s",
            user_id,
            monitor.id,
            error_message,
        )
        monitor.last_error = error_message
        monitor.last_error_at = utcnow_iso()
        self._repository.save_monitor(user_id, monitor)

    def _should_notify_error(self, key: str, error_message: str) -> bool:
        now = asyncio.get_running_loop().time()
        entry_key = (key, error_message)
        last_sent_at = self._last_error_notification_at.get(entry_key)
        if (
            last_sent_at is not None
            and now - last_sent_at < ERROR_NOTIFICATION_COOLDOWN_SECONDS
        ):
            return False

        self._last_error_notification_at[entry_key] = now
        stale_before = now - (ERROR_NOTIFICATION_COOLDOWN_SECONDS * 3)
        self._last_error_notification_at = {
            item_key: item_sent_at
            for item_key, item_sent_at in self._last_error_notification_at.items()
            if item_sent_at >= stale_before
        }
        return True

    # -- Notification --------------------------------------------------------

    async def _emit(
        self,
        user_id: str,
        monitor: P2PMonitorChatState,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        payload = {"monitor_id": monitor.id, "monitor_name": monitor.name, **data}
        try:
            await self._notifier.emit(
                MonitorEvent(type=event_type, user_id=user_id, data=payload)
            )
        except Exception:  # noqa: BLE001
            LOGGER.exception(
                "Failed to emit monitor event user_id=%s monitor_id=%s type=%s",
                user_id,
                monitor.id,
                event_type,
            )

    def _build_backoff_seconds(self, monitor: P2PMonitorChatState) -> float:
        base_value = max(monitor.poll_interval_seconds, MIN_P2P_POLL_INTERVAL_SECONDS)
        return float(base_value + random.uniform(1, 5))

    def _prune_apply_window(self) -> None:
        now = asyncio.get_running_loop().time()
        while self._recent_apply_attempts and now - self._recent_apply_attempts[0] > 60:
            self._recent_apply_attempts.popleft()


def _extract_error_message(body: Any) -> str | None:
    if isinstance(body, dict):
        for key in ("error", "message", "info"):
            value = body.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    if isinstance(body, str) and body.strip():
        return body.strip()
    return None
