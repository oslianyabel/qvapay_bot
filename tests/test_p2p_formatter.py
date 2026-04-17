from __future__ import annotations

from qvapay_bot.p2p_formatter import format_applied_history, format_monitor_status
from qvapay_bot.p2p_models import (
    OfferHistoryEntry,
    OfferProcessResult,
    P2PMonitorChatState,
)


# uv run pytest -s tests/test_p2p_formatter.py
def test_format_monitor_status_includes_rules_and_errors() -> None:
    state = P2PMonitorChatState(enabled=True, poll_interval_seconds=30)
    state.rules.coin = "BANK_CUP"
    state.last_error = "sample error"
    state.last_error_at = "2026-04-02T10:00:00Z"

    formatted = format_monitor_status(state)

    assert "enabled: yes" in formatted
    assert "coin: BANK_CUP" in formatted
    assert "last_error: sample error" in formatted


# uv run pytest -s tests/test_p2p_formatter.py
def test_format_applied_history_groups_applied_and_lost_race_entries() -> None:
    applied_entry = OfferHistoryEntry(
        uuid="offer-1",
        status="processing",
        coin="BANK_CUP",
        amount=50,
        receive=13500,
        ratio=270,
        user_uuid="user-1",
        username="alice",
        evaluated_at="2026-04-02T10:00:00Z",
        first_detected_at="2026-04-02T09:59:00Z",
        result=OfferProcessResult.APPLIED,
        reason="Offer applied successfully.",
    )
    lost_entry = OfferHistoryEntry(
        uuid="offer-2",
        status="open",
        coin="BANK_CUP",
        amount=40,
        receive=10500,
        ratio=262.5,
        user_uuid="user-2",
        username="bob",
        evaluated_at="2026-04-02T10:05:00Z",
        first_detected_at="2026-04-02T10:04:00Z",
        result=OfferProcessResult.LOST_RACE,
        reason="Offer was taken by another peer first.",
    )

    formatted = format_applied_history([applied_entry], [lost_entry])

    assert "applied:" in formatted
    assert "lost_race:" in formatted
    assert "offer-1" in formatted
    assert "offer-2" in formatted
