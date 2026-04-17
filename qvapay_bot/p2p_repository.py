from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from qvapay_bot.p2p_models import (
    DEFAULT_P2P_POLL_INTERVAL_SECONDS,
    MAX_HISTORY_ITEMS,
    MAX_SEEN_OFFERS,
    OfferHistoryEntry,
    OfferProcessResult,
    P2PMonitorChatState,
    P2PMonitorRules,
    P2POfferType,
)


class P2PMonitorStateStore:
    def __init__(self, file_path: Path) -> None:
        self._file_path = file_path
        self._chats: dict[str, P2PMonitorChatState] = {}
        self._load()

    def get_chat_state(self, chat_id: int) -> P2PMonitorChatState:
        key = str(chat_id)
        if key not in self._chats:
            self._chats[key] = P2PMonitorChatState()
        return self._chats[key]

    def save_chat_state(self, chat_id: int, state: P2PMonitorChatState) -> None:
        self._chats[str(chat_id)] = state
        self._save()

    def list_enabled_chat_ids(self) -> list[int]:
        return [int(chat_id) for chat_id, state in self._chats.items() if state.enabled]

    def find_history_entry(
        self, chat_id: int, offer_uuid: str
    ) -> OfferHistoryEntry | None:
        state = self.get_chat_state(chat_id)
        for collection in (
            state.applied_history,
            state.lost_race_history,
            state.notified_history,
            state.filtered_history,
            state.discarded_history,
        ):
            for entry in collection:
                if entry.uuid == offer_uuid:
                    return entry
        return None

    def _load(self) -> None:
        if not self._file_path.exists():
            return

        raw_payload = json.loads(self._file_path.read_text(encoding="utf-8"))
        chats = raw_payload.get("chats", {})
        self._chats = {
            chat_id: _chat_state_from_dict(value)
            for chat_id, value in chats.items()
            if isinstance(chat_id, str) and isinstance(value, dict)
        }

    def _save(self) -> None:
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "chats": {
                chat_id: _chat_state_to_dict(state)
                for chat_id, state in self._chats.items()
            },
        }
        self._file_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )


def _chat_state_from_dict(raw_state: dict[str, Any]) -> P2PMonitorChatState:
    rules_raw = (
        raw_state.get("rules") if isinstance(raw_state.get("rules"), dict) else {}
    )
    target_type_raw = str(raw_state.get("target_type", P2POfferType.ANY.value))
    try:
        target_type = P2POfferType(target_type_raw)
    except ValueError:
        target_type = P2POfferType.ANY

    return P2PMonitorChatState(
        enabled=bool(raw_state.get("enabled", False)),
        poll_interval_seconds=_coerce_int(
            raw_state.get("poll_interval_seconds"),
            DEFAULT_P2P_POLL_INTERVAL_SECONDS,
        ),
        target_type=target_type,
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


def _chat_state_to_dict(state: P2PMonitorChatState) -> dict[str, Any]:
    return {
        "enabled": state.enabled,
        "poll_interval_seconds": state.poll_interval_seconds,
        "target_type": state.target_type.value,
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
