from __future__ import annotations

import asyncio
import logging
import random
from collections import deque
from typing import TYPE_CHECKING, Any

from qvapay_bot.config import Settings
from qvapay_bot.p2p_filters import (
    build_offer_snapshot,
    evaluate_offer,
    sort_eligible_offers,
    summarize_discarded_reasons,
)
from qvapay_bot.p2p_formatter import format_offer_notification
from qvapay_bot.p2p_models import (
    MAX_HISTORY_ITEMS,
    MIN_P2P_POLL_INTERVAL_SECONDS,
    OfferEvaluation,
    OfferProcessResult,
    P2PMonitorChatState,
    P2PMonitorCycleReport,
    P2POfferSnapshot,
    P2POfferType,
    offer_history_from_offer,
    trim_history,
    utcnow_iso,
)
from qvapay_bot.p2p_repository import P2PMonitorStateStore
from qvapay_bot.qvapay_client import COMMAND_INDEX, QvaPayClient
from qvapay_bot.state import BotStateStore, ChatAuthState

if TYPE_CHECKING:
    from telegram import Bot
    from telegram.ext import JobQueue

LOGGER = logging.getLogger(__name__)


def _job_name(chat_id: int) -> str:
    return f"p2p_monitor_{chat_id}"


class P2PMonitorManager:
    def __init__(
        self,
        *,
        settings: Settings,
        state_store: BotStateStore,
        repository: P2PMonitorStateStore,
        qvapay_client: QvaPayClient,
    ) -> None:
        self._settings = settings
        self._state_store = state_store
        self._repository = repository
        self._qvapay_client = qvapay_client
        self._recent_apply_attempts: deque[float] = deque()
        self._apply_lock = asyncio.Lock()

    async def restore_jobs(self, job_queue: JobQueue | None) -> None:  # type: ignore[type-arg]
        if job_queue is None:
            return
        restored = 0
        for chat_id, auth_state in self._state_store.iter_chat_states():
            chat_state = self._repository.get_chat_state(chat_id)
            if chat_state.enabled and auth_state.has_bearer:
                self._schedule_job(chat_id, chat_state.poll_interval_seconds, job_queue)
                restored += 1
        LOGGER.info("P2P monitor jobs restored count=%s", restored)

    async def restart_chat(
        self,
        chat_id: int,
        auth_state: ChatAuthState,
        job_queue: JobQueue | None,  # type: ignore[type-arg]
    ) -> None:
        await self.stop_chat(chat_id, job_queue)
        chat_state = self._repository.get_chat_state(chat_id)
        if chat_state.enabled and auth_state.has_bearer and job_queue is not None:
            LOGGER.info(
                "Starting P2P monitor job chat_id=%s interval_seconds=%s",
                chat_id,
                chat_state.poll_interval_seconds,
            )
            self._schedule_job(chat_id, chat_state.poll_interval_seconds, job_queue)
        else:
            LOGGER.info(
                "P2P monitor job not started chat_id=%s enabled=%s has_bearer=%s",
                chat_id,
                chat_state.enabled,
                auth_state.has_bearer,
            )

    async def stop_chat(self, chat_id: int, job_queue: JobQueue | None) -> None:  # type: ignore[type-arg]
        if job_queue is None:
            return
        name = _job_name(chat_id)
        jobs = job_queue.get_jobs_by_name(name)
        for job in jobs:
            job.schedule_removal()
        if jobs:
            LOGGER.info("Stopped P2P monitor job chat_id=%s", chat_id)

    async def run_cycle_once(
        self,
        chat_id: int,
        auth_state: ChatAuthState,
        *,
        force: bool,
        notify: bool,
        bot: Bot | None = None,
    ) -> P2PMonitorCycleReport:
        report = P2PMonitorCycleReport()
        chat_state = self._repository.get_chat_state(chat_id)
        if not force and not chat_state.enabled:
            report.error_message = "P2P monitor is disabled for this chat."
            return report
        if not auth_state.has_bearer:
            error_message = "A bearer token is required to monitor P2P offers."
            self._set_error(chat_id, chat_state, error_message)
            report.error_message = error_message
            return report

        LOGGER.info(
            "Starting P2P monitor cycle chat_id=%s force=%s notify=%s target_type=%s coin=%s",
            chat_id,
            force,
            notify,
            chat_state.target_type.value,
            chat_state.rules.coin or "any",
        )

        await self._ensure_user_profile(chat_id, auth_state)
        response = await self._qvapay_client.execute(
            COMMAND_INDEX["list_p2p"],
            self._build_list_arguments(chat_state),
            auth_state,
        )
        if response.status_code == 429:
            report.rate_limited = True
            report.error_message = "QvaPay rate limit reached while reading P2P offers."
            report.next_sleep_seconds = self._build_backoff_seconds(chat_state)
            self._set_error(chat_id, chat_state, report.error_message)
            return report
        if response.status_code >= 400:
            report.error_message = (
                f"Unable to read P2P offers. HTTP {response.status_code}."
            )
            self._set_error(chat_id, chat_state, report.error_message)
            return report

        offers_raw = None
        if isinstance(response.body, dict):
            offers_raw = response.body.get("data") or response.body.get("offers")
        if not isinstance(offers_raw, list):
            LOGGER.error(
                "Invalid /p2p payload chat_id=%s status_code=%s body=%r",
                chat_id,
                response.status_code,
                response.body,
            )
            report.error_message = "QvaPay returned an invalid payload for /p2p."
            self._set_error(chat_id, chat_state, report.error_message)
            return report

        offers = [
            offer
            for item in offers_raw
            if (offer := build_offer_snapshot(item)) is not None
        ]
        evaluations = [
            evaluate_offer(
                offer,
                chat_state.rules,
                target_type=chat_state.target_type,
                current_user_uuid=auth_state.user_uuid,
                processed_offer_timestamps=chat_state.processed_offer_timestamps,
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
            "Fetched P2P offers chat_id=%s read=%s eligible=%s discarded=%s top_discarded=%s",
            chat_id,
            report.read_count,
            report.filtered_count,
            report.discarded_count,
            ", ".join(report.top_discarded_reasons) or "none",
        )
        self._log_cycle_evaluations(chat_id, evaluations)

        evaluated_at = utcnow_iso()
        self._remember_cycle_entries(chat_state, evaluations, evaluated_at)

        sorted_candidates = sort_eligible_offers(evaluations, chat_state.rules)

        if chat_state.target_type == P2POfferType.BUY and sorted_candidates:
            balance = await self.fetch_balance(auth_state)
            if balance is not None:
                if balance < 1:
                    LOGGER.info(
                        "Balance too low to buy chat_id=%s balance=%.2f, stopping monitor",
                        chat_id,
                        balance,
                    )
                    chat_state.enabled = False
                    self._repository.save_chat_state(chat_id, chat_state)
                    await self._send_text(
                        bot,
                        chat_id,
                        f"⚠️ Saldo insuficiente ({balance:.2f} QUSD). Monitoreo detenido.",
                    )
                    report.error_message = "Balance too low."
                    return report
                sorted_candidates = [
                    o for o in sorted_candidates if o.amount <= balance
                ]

        if not sorted_candidates:
            LOGGER.info("No eligible P2P offers found for chat_id=%s", chat_id)
            chat_state.last_error = None
            chat_state.last_error_at = None
            chat_state.last_success_at = evaluated_at
            self._repository.save_chat_state(chat_id, chat_state)
            return report

        selected_offer = sorted_candidates[0]
        LOGGER.info(
            "Selected P2P offer chat_id=%s uuid=%s ratio=%.6f amount=%.2f coin=%s advertiser=%s",
            chat_id,
            selected_offer.uuid,
            selected_offer.ratio,
            selected_offer.amount,
            selected_offer.coin,
            selected_offer.advertiser.username
            or selected_offer.advertiser.uuid
            or "unknown",
        )
        first_detected_at = self._remember_first_seen(
            chat_state, selected_offer.uuid, evaluated_at
        )
        matched_entry = offer_history_from_offer(
            selected_offer,
            evaluated_at=evaluated_at,
            first_detected_at=first_detected_at,
            result=OfferProcessResult.MATCHED,
        )
        report.matched_entry = matched_entry
        chat_state.notified_history = trim_history(
            [matched_entry, *chat_state.notified_history]
        )

        final_entry = await self._attempt_apply(
            chat_id,
            chat_state,
            auth_state,
            selected_offer,
            evaluated_at,
            first_detected_at,
        )
        report.final_entry = final_entry
        chat_state.last_error = None
        chat_state.last_error_at = None
        chat_state.last_success_at = evaluated_at
        self._repository.save_chat_state(chat_id, chat_state)

        if notify and bot is not None:
            text, keyboard = format_offer_notification(
                selected_offer,
                evaluated_at=evaluated_at,
                result_text=f"{final_entry.result.value}: {final_entry.reason or '-'}",
                result=final_entry.result,
            )
            await self._send_message_with_keyboard(bot, chat_id, text, keyboard)

        if (
            chat_state.target_type == P2POfferType.BUY
            and final_entry.result == OfferProcessResult.APPLIED
        ):
            post_balance = await self.fetch_balance(auth_state)
            if post_balance is not None and post_balance < 1:
                chat_state.enabled = False
                self._repository.save_chat_state(chat_id, chat_state)
                if bot is not None:
                    await self._send_text(
                        bot,
                        chat_id,
                        f"⚠️ Saldo insuficiente ({post_balance:.2f} QUSD). Monitoreo detenido.",
                    )

        return report

    def _schedule_job(
        self,
        chat_id: int,
        interval_seconds: int,
        job_queue: JobQueue,  # type: ignore[type-arg]
    ) -> None:
        name = _job_name(chat_id)
        # Remove existing jobs for this chat
        for job in job_queue.get_jobs_by_name(name):
            job.schedule_removal()
        job_queue.run_repeating(
            self._job_callback,
            interval=max(interval_seconds, MIN_P2P_POLL_INTERVAL_SECONDS),
            first=1,
            name=name,
            data={"chat_id": chat_id},
        )

    async def _job_callback(self, context: Any) -> None:
        job = context.job
        chat_id: int = job.data["chat_id"]
        bot: Bot = context.bot

        chat_state = self._repository.get_chat_state(chat_id)
        auth_state = self._state_store.get_chat_state(chat_id)
        if not chat_state.enabled or not auth_state.has_bearer:
            job.schedule_removal()
            return

        previous_error = chat_state.last_error
        try:
            report = await self.run_cycle_once(
                chat_id,
                auth_state,
                force=False,
                notify=True,
                bot=bot,
            )
            if report.error_message and report.error_message != previous_error:
                await self._notify_error(bot, chat_id, report.error_message)
        except Exception as exc:
            error_message = f"Unhandled P2P monitor error: {exc}"
            LOGGER.exception(
                "Unhandled exception in P2P job chat_id=%s",
                chat_id,
            )
            self._set_error(chat_id, chat_state, error_message)
            if error_message != previous_error:
                await self._notify_error(bot, chat_id, error_message)

    async def _attempt_apply(
        self,
        chat_id: int,
        chat_state: P2PMonitorChatState,
        auth_state: ChatAuthState,
        offer: P2POfferSnapshot,
        evaluated_at: str,
        first_detected_at: str,
    ) -> Any:
        applied_at = utcnow_iso()
        async with self._apply_lock:
            self._prune_apply_window()
            if len(self._recent_apply_attempts) >= 2:
                LOGGER.info(
                    "Skipping P2P apply due to local throttle chat_id=%s uuid=%s",
                    chat_id,
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
                chat_state.processed_offer_timestamps[offer.uuid] = applied_at
                chat_state.applied_history = trim_history(
                    [entry, *chat_state.applied_history]
                )
                return entry
            self._recent_apply_attempts.append(asyncio.get_running_loop().time())

        LOGGER.info(
            "Attempting to apply P2P offer chat_id=%s uuid=%s ratio=%.6f amount=%.2f coin=%s",
            chat_id,
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
            "P2P apply result chat_id=%s uuid=%s status_code=%s result=%s reason=%s",
            chat_id,
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
        chat_state.processed_offer_timestamps[offer.uuid] = applied_at
        chat_state.seen_offer_ids = [
            offer.uuid,
            *[item for item in chat_state.seen_offer_ids if item != offer.uuid],
        ][:100]
        if target_history == "lost_race":
            chat_state.lost_race_history = trim_history(
                [entry, *chat_state.lost_race_history]
            )
        else:
            chat_state.applied_history = trim_history(
                [entry, *chat_state.applied_history]
            )
        return entry

    async def _ensure_user_profile(
        self, chat_id: int, auth_state: ChatAuthState
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
        self._state_store.save_chat_state(chat_id, auth_state)

    async def fetch_balance(self, auth_state: ChatAuthState) -> float | None:
        if not auth_state.has_bearer:
            return None
        response = await self._qvapay_client.execute(
            COMMAND_INDEX["profile"],
            {},
            auth_state,
        )
        if response.status_code == 200 and isinstance(response.body, dict):
            balance = response.body.get("balance")
            if isinstance(balance, (int, float)):
                return float(balance)
        return None

    def _build_list_arguments(self, chat_state: P2PMonitorChatState) -> dict[str, Any]:
        arguments: dict[str, Any] = {
            "page": 1,
            "take": 100,
            "status": "open",
        }
        if chat_state.target_type != P2POfferType.ANY:
            arguments["type"] = chat_state.target_type.value
        if chat_state.rules.coin:
            arguments["coin"] = chat_state.rules.coin
        return arguments

    def _remember_cycle_entries(
        self,
        chat_state: P2PMonitorChatState,
        evaluations: list[OfferEvaluation],
        evaluated_at: str,
    ) -> None:
        filtered_entries = []
        discarded_entries = []
        for evaluation in evaluations[:MAX_HISTORY_ITEMS]:
            first_detected_at = self._remember_first_seen(
                chat_state, evaluation.offer.uuid, evaluated_at
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

        chat_state.filtered_history = trim_history(
            filtered_entries + chat_state.filtered_history
        )
        chat_state.discarded_history = trim_history(
            discarded_entries + chat_state.discarded_history
        )

    def _log_cycle_evaluations(
        self,
        chat_id: int,
        evaluations: list[OfferEvaluation],
    ) -> None:
        for evaluation in evaluations:
            offer = evaluation.offer
            LOGGER.info(
                "P2P offer evaluated chat_id=%s uuid=%s type=%s coin=%s amount=%.2f receive=%.2f ratio=%.6f advertiser=%s eligible=%s reasons=%s",
                chat_id,
                offer.uuid,
                offer.offer_type.value,
                offer.coin,
                offer.amount,
                offer.receive,
                offer.ratio,
                offer.advertiser.username or offer.advertiser.uuid or "unknown",
                evaluation.is_eligible,
                ", ".join(evaluation.reasons) or "passed_all_filters",
            )

    def _remember_first_seen(
        self,
        chat_state: P2PMonitorChatState,
        offer_uuid: str,
        detected_at: str,
    ) -> str:
        if offer_uuid not in chat_state.first_seen_at_by_offer:
            chat_state.first_seen_at_by_offer[offer_uuid] = detected_at
        return chat_state.first_seen_at_by_offer[offer_uuid]

    def _set_error(
        self,
        chat_id: int,
        chat_state: P2PMonitorChatState,
        error_message: str,
    ) -> None:
        LOGGER.error("P2P monitor error chat_id=%s message=%s", chat_id, error_message)
        chat_state.last_error = error_message
        chat_state.last_error_at = utcnow_iso()
        self._repository.save_chat_state(chat_id, chat_state)

    async def _notify_error(self, bot: Bot, chat_id: int, error_message: str) -> None:
        await self._send_text(bot, chat_id, error_message)
        if self._settings.telegram_dev_chat_id is not None:
            await self._send_text(
                bot,
                self._settings.telegram_dev_chat_id,
                f"chat_id={chat_id}\n{error_message}",
            )

    @staticmethod
    async def _send_text(bot: Bot, chat_id: int, text: str) -> None:
        await bot.send_message(chat_id=chat_id, text=text)

    @staticmethod
    async def _send_message_with_keyboard(
        bot: Bot,
        chat_id: int,
        text: str,
        keyboard_rows: list[list[dict[str, str]]],
    ) -> None:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        inline_keyboard = [
            [
                InlineKeyboardButton(
                    text=btn["text"], callback_data=btn["callback_data"]
                )
                for btn in row
            ]
            for row in keyboard_rows
        ]
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard),
            parse_mode="HTML",
        )

    def _build_backoff_seconds(self, chat_state: P2PMonitorChatState) -> float:
        base_value = max(
            chat_state.poll_interval_seconds, MIN_P2P_POLL_INTERVAL_SECONDS
        )
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
