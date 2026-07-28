"""Serialización de dataclasses del dominio P2P a dicts JSON-friendly.

Reutilizado por el monitor (payloads de eventos SSE) y por los routers de la web app.
"""

from __future__ import annotations

from typing import Any

from qvapay_bot.p2p_models import (
    OfferEvaluation,
    OfferHistoryEntry,
    P2PMonitorChatState,
    P2PMonitorCycleReport,
    P2PMonitorRules,
    P2POfferSnapshot,
)

QVAPAY_P2P_URL = "https://www.qvapay.com/p2p-pub/"


def offer_link(uuid: str) -> str:
    return f"{QVAPAY_P2P_URL}{uuid}"


def offer_snapshot_to_dict(offer: P2POfferSnapshot) -> dict[str, Any]:
    return {
        "uuid": offer.uuid,
        "offer_type": offer.offer_type.value,
        "coin": offer.coin,
        "amount": offer.amount,
        "receive": offer.receive,
        "ratio": offer.ratio,
        "status": offer.status,
        "only_kyc": offer.only_kyc,
        "only_vip": offer.only_vip,
        "created_at": offer.created_at,
        "link": offer_link(offer.uuid),
        "advertiser": {
            "uuid": offer.advertiser.uuid,
            "username": offer.advertiser.username,
            "kyc": offer.advertiser.kyc,
            "vip": offer.advertiser.vip,
        },
    }


def history_entry_to_dict(entry: OfferHistoryEntry) -> dict[str, Any]:
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
        "link": offer_link(entry.uuid),
    }


def rules_to_dict(rules: P2PMonitorRules) -> dict[str, Any]:
    return {
        "coin": rules.coin,
        "min_ratio": rules.min_ratio,
        "max_ratio": rules.max_ratio,
        "min_amount": rules.min_amount,
        "max_amount": rules.max_amount,
        "only_kyc": rules.only_kyc,
        "only_vip": rules.only_vip,
    }


def evaluation_to_dict(evaluation: OfferEvaluation) -> dict[str, Any]:
    return {
        "offer": offer_snapshot_to_dict(evaluation.offer),
        "is_eligible": evaluation.is_eligible,
        "reasons": list(evaluation.reasons),
    }


def cycle_report_to_dict(report: P2PMonitorCycleReport) -> dict[str, Any]:
    return {
        "read_count": report.read_count,
        "filtered_count": report.filtered_count,
        "discarded_count": report.discarded_count,
        "top_discarded_reasons": list(report.top_discarded_reasons),
        "error_message": report.error_message,
        "rate_limited": report.rate_limited,
        "next_sleep_seconds": report.next_sleep_seconds,
        "applied_rules": (
            rules_to_dict(report.applied_rules)
            if report.applied_rules is not None
            else None
        ),
        "selected_offer": (
            offer_snapshot_to_dict(report.selected_offer)
            if report.selected_offer is not None
            else None
        ),
        "matched_entry": (
            history_entry_to_dict(report.matched_entry)
            if report.matched_entry is not None
            else None
        ),
        "final_entry": (
            history_entry_to_dict(report.final_entry)
            if report.final_entry is not None
            else None
        ),
    }


def monitor_state_to_dict(
    state: P2PMonitorChatState,
    *,
    balance: float | None = None,
) -> dict[str, Any]:
    """Vista pública del estado de un monitor para los endpoints /api/monitors."""
    applied_count = len(state.applied_history)
    return {
        "id": state.id,
        "name": state.name,
        "enabled": state.enabled,
        "poll_interval_seconds": state.poll_interval_seconds,
        "target_type": state.target_type.value,
        "rules": rules_to_dict(state.rules),
        "last_error": state.last_error,
        "last_error_at": state.last_error_at,
        "last_success_at": state.last_success_at,
        "applied_count": applied_count,
        "balance": balance,
    }
