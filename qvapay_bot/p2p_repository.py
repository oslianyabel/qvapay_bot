from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from qvapay_bot.p2p_models import (
    DEFAULT_P2P_POLL_INTERVAL_SECONDS,
    MAX_HISTORY_ITEMS,
    MAX_SEEN_OFFERS,
    ApplyMode,
    OfferHistoryEntry,
    OfferProcessResult,
    P2PMonitorChatState,
    P2PMonitorRules,
    P2POfferType,
    SelectionStrategy,
)


def _new_monitor_id() -> str:
    return uuid.uuid4().hex


class P2PMonitorStateStore:
    """Persistencia de monitores P2P.

    Estructura en disco (v2):
        {"version": 2, "users": {user_id: {"monitors": {monitor_id: {...}}}}}

    Cada usuario puede tener varios monitores independientes.
    """

    def __init__(self, file_path: Path) -> None:
        self._file_path = file_path
        self._users: dict[str, dict[str, P2PMonitorChatState]] = {}
        self._load()

    # -- Reads ---------------------------------------------------------------

    def list_monitors(self, user_id: str) -> list[P2PMonitorChatState]:
        return list(self._users.get(str(user_id), {}).values())

    def get_monitor(
        self, user_id: str, monitor_id: str
    ) -> P2PMonitorChatState | None:
        return self._users.get(str(user_id), {}).get(monitor_id)

    def iter_all_enabled(self) -> list[tuple[str, P2PMonitorChatState]]:
        result: list[tuple[str, P2PMonitorChatState]] = []
        for user_id, monitors in self._users.items():
            for monitor in monitors.values():
                if monitor.enabled:
                    result.append((user_id, monitor))
        return result

    def find_history_entry(
        self, user_id: str, monitor_id: str, offer_uuid: str
    ) -> OfferHistoryEntry | None:
        monitor = self.get_monitor(user_id, monitor_id)
        if monitor is None:
            return None
        for collection in (
            monitor.applied_history,
            monitor.lost_race_history,
            monitor.notified_history,
            monitor.filtered_history,
            monitor.discarded_history,
        ):
            for entry in collection:
                if entry.uuid == offer_uuid:
                    return entry
        return None

    # -- Writes --------------------------------------------------------------

    def create_monitor(self, user_id: str, name: str) -> P2PMonitorChatState:
        monitor = P2PMonitorChatState(id=_new_monitor_id(), name=name.strip() or "Monitor")
        self._users.setdefault(str(user_id), {})[monitor.id] = monitor
        self._save()
        return monitor

    def save_monitor(self, user_id: str, monitor: P2PMonitorChatState) -> None:
        if not monitor.id:
            monitor.id = _new_monitor_id()
        self._users.setdefault(str(user_id), {})[monitor.id] = monitor
        self._save()

    def delete_monitor(self, user_id: str, monitor_id: str) -> bool:
        monitors = self._users.get(str(user_id))
        if not monitors or monitor_id not in monitors:
            return False
        del monitors[monitor_id]
        if not monitors:
            self._users.pop(str(user_id), None)
        self._save()
        return True

    # -- Persistence ---------------------------------------------------------

    def _load(self) -> None:
        if not self._file_path.exists():
            return

        raw_payload = json.loads(self._file_path.read_text(encoding="utf-8"))
        version = raw_payload.get("version")

        if version == 2 and isinstance(raw_payload.get("users"), dict):
            for user_id, user_blob in raw_payload["users"].items():
                if not isinstance(user_id, str) or not isinstance(user_blob, dict):
                    continue
                monitors_raw = user_blob.get("monitors", {})
                if not isinstance(monitors_raw, dict):
                    continue
                monitors: dict[str, P2PMonitorChatState] = {}
                for monitor_id, value in monitors_raw.items():
                    if not isinstance(monitor_id, str) or not isinstance(value, dict):
                        continue
                    monitor = _monitor_from_dict(value)
                    monitor.id = monitor.id or monitor_id
                    monitors[monitor.id] = monitor
                self._users[user_id] = monitors
            return

        # Migración desde v1: {"version":1, "chats": {user_id: {monitor fields}}}
        chats = raw_payload.get("chats", {})
        if isinstance(chats, dict):
            for user_id, value in chats.items():
                if not isinstance(user_id, str) or not isinstance(value, dict):
                    continue
                monitor = _monitor_from_dict(value)
                monitor.id = monitor.id or _new_monitor_id()
                monitor.name = monitor.name or "Principal"
                self._users[user_id] = {monitor.id: monitor}
            self._save()

    def _save(self) -> None:
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 2,
            "users": {
                user_id: {
                    "monitors": {
                        monitor_id: _monitor_to_dict(monitor)
                        for monitor_id, monitor in monitors.items()
                    }
                }
                for user_id, monitors in self._users.items()
            },
        }
        self._file_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )


def _monitor_from_dict(raw_state: dict[str, Any]) -> P2PMonitorChatState:
    raw_rules = raw_state.get("rules")
    rules_raw: dict[str, Any] = raw_rules if isinstance(raw_rules, dict) else {}
    target_type_raw = str(raw_state.get("target_type", P2POfferType.ANY.value))
    try:
        target_type = P2POfferType(target_type_raw)
    except ValueError:
        target_type = P2POfferType.ANY

    try:
        selection_strategy = SelectionStrategy(
            str(raw_state.get("selection_strategy", SelectionStrategy.BEST_RATIO.value))
        )
    except ValueError:
        selection_strategy = SelectionStrategy.BEST_RATIO

    try:
        apply_mode = ApplyMode(
            str(raw_state.get("apply_mode", ApplyMode.SINGLE.value))
        )
    except ValueError:
        apply_mode = ApplyMode.SINGLE

    return P2PMonitorChatState(
        id=_coerce_optional_str(raw_state.get("id")) or "",
        name=_coerce_optional_str(raw_state.get("name")) or "",
        enabled=bool(raw_state.get("enabled", False)),
        poll_interval_seconds=_coerce_int(
            raw_state.get("poll_interval_seconds"),
            DEFAULT_P2P_POLL_INTERVAL_SECONDS,
        ),
        target_type=target_type,
        selection_strategy=selection_strategy,
        apply_mode=apply_mode,
        rules=P2PMonitorRules(
            coin=_coerce_optional_str(rules_raw.get("coin")),
            min_ratio=_coerce_optional_float(rules_raw.get("min_ratio")),
            max_ratio=_coerce_optional_float(rules_raw.get("max_ratio")),
            min_amount=_coerce_optional_float(rules_raw.get("min_amount")),
            max_amount=_coerce_optional_float(rules_raw.get("max_amount")),
            only_kyc=bool(rules_raw.get("only_kyc", False)),
            only_vip=bool(rules_raw.get("only_vip", False)),
        ),
        seen_offer_ids=_coerce_str_list(raw_state.get("seen_offer_ids"))[
            :MAX_SEEN_OFFERS
        ],
        first_seen_at_by_offer=_coerce_str_dict(
            raw_state.get("first_seen_at_by_offer")
        ),
        processed_offer_timestamps=_coerce_str_dict(
            raw_state.get("processed_offer_timestamps")
        ),
        filtered_history=_history_from_raw(raw_state.get("filtered_history")),
        discarded_history=_history_from_raw(raw_state.get("discarded_history")),
        notified_history=_history_from_raw(raw_state.get("notified_history")),
        applied_history=_history_from_raw(raw_state.get("applied_history")),
        lost_race_history=_history_from_raw(raw_state.get("lost_race_history")),
        last_error=_coerce_optional_str(raw_state.get("last_error")),
        last_error_at=_coerce_optional_str(raw_state.get("last_error_at")),
        last_success_at=_coerce_optional_str(raw_state.get("last_success_at")),
    )


def _monitor_to_dict(state: P2PMonitorChatState) -> dict[str, Any]:
    return {
        "id": state.id,
        "name": state.name,
        "enabled": state.enabled,
        "poll_interval_seconds": state.poll_interval_seconds,
        "target_type": state.target_type.value,
        "selection_strategy": state.selection_strategy.value,
        "apply_mode": state.apply_mode.value,
        "rules": {
            "coin": state.rules.coin,
            "min_ratio": state.rules.min_ratio,
            "max_ratio": state.rules.max_ratio,
            "min_amount": state.rules.min_amount,
            "max_amount": state.rules.max_amount,
            "only_kyc": state.rules.only_kyc,
            "only_vip": state.rules.only_vip,
        },
        "seen_offer_ids": state.seen_offer_ids[:MAX_SEEN_OFFERS],
        "first_seen_at_by_offer": state.first_seen_at_by_offer,
        "processed_offer_timestamps": state.processed_offer_timestamps,
        "filtered_history": [
            _history_to_dict(entry)
            for entry in state.filtered_history[:MAX_HISTORY_ITEMS]
        ],
        "discarded_history": [
            _history_to_dict(entry)
            for entry in state.discarded_history[:MAX_HISTORY_ITEMS]
        ],
        "notified_history": [
            _history_to_dict(entry)
            for entry in state.notified_history[:MAX_HISTORY_ITEMS]
        ],
        "applied_history": [
            _history_to_dict(entry)
            for entry in state.applied_history[:MAX_HISTORY_ITEMS]
        ],
        "lost_race_history": [
            _history_to_dict(entry)
            for entry in state.lost_race_history[:MAX_HISTORY_ITEMS]
        ],
        "last_error": state.last_error,
        "last_error_at": state.last_error_at,
        "last_success_at": state.last_success_at,
    }


def _history_from_raw(raw_history: Any) -> list[OfferHistoryEntry]:
    if not isinstance(raw_history, list):
        return []

    entries: list[OfferHistoryEntry] = []
    for raw_entry in raw_history[:MAX_HISTORY_ITEMS]:
        if not isinstance(raw_entry, dict):
            continue
        result_raw = raw_entry.get("result")
        result: OfferProcessResult | None = None
        if isinstance(result_raw, str) and result_raw:
            try:
                result = OfferProcessResult(result_raw)
            except ValueError:
                result = None
        entries.append(
            OfferHistoryEntry(
                uuid=str(raw_entry.get("uuid", "")),
                status=str(raw_entry.get("status", "")),
                coin=str(raw_entry.get("coin", "")),
                amount=float(raw_entry.get("amount", 0)),
                receive=float(raw_entry.get("receive", 0)),
                ratio=float(raw_entry.get("ratio", 0)),
                user_uuid=_coerce_optional_str(raw_entry.get("user_uuid")),
                username=_coerce_optional_str(raw_entry.get("username")),
                evaluated_at=str(raw_entry.get("evaluated_at", "")),
                first_detected_at=str(raw_entry.get("first_detected_at", "")),
                notified_at=_coerce_optional_str(raw_entry.get("notified_at")),
                applied_at=_coerce_optional_str(raw_entry.get("applied_at")),
                result=result,
                reason=_coerce_optional_str(raw_entry.get("reason")),
            )
        )
    return entries


def _history_to_dict(entry: OfferHistoryEntry) -> dict[str, Any]:
    return {
        "uuid": entry.uuid,
        "status": entry.status,
        "coin": entry.coin,
        "amount": entry.amount,
        "receive": entry.receive,
        "ratio": entry.ratio,
        "user_uuid": entry.user_uuid,
        "username": entry.username,
        "evaluated_at": entry.evaluated_at,
        "first_detected_at": entry.first_detected_at,
        "notified_at": entry.notified_at,
        "applied_at": entry.applied_at,
        "result": entry.result.value if entry.result is not None else None,
        "reason": entry.reason,
    }


def _coerce_optional_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _coerce_optional_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _coerce_int(value: Any, default: int) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return default


def _coerce_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def _coerce_str_dict(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {
        str(key): str(item)
        for key, item in value.items()
        if isinstance(key, str)
        and isinstance(item, str)
        and key.strip()
        and item.strip()
    }
