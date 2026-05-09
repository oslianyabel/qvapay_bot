from __future__ import annotations

from pathlib import Path

from qvapay_bot.p2p_models import OfferHistoryEntry, OfferProcessResult, P2POfferType
from qvapay_bot.p2p_repository import P2PMonitorStateStore


# uv run pytest -s tests/test_p2p_repository.py
def test_repository_persists_monitor_state(tmp_path: Path) -> None:
    repository = P2PMonitorStateStore(tmp_path / "p2p_state.json")

    state = repository.get_chat_state(100)
    state.enabled = True
    state.poll_interval_seconds = 45
    state.target_type = P2POfferType.SELL
    state.rules.coin = "BANK_CUP"
    state.applied_history.append(
        OfferHistoryEntry(
            uuid="offer-1",
            status="processing",
            coin="BANK_CUP",
            amount=50,
            receive=13500,
            ratio=270,
            user_uuid="user-1",
            username="alice",
            evaluated_at="2026-04-02T10:00:00Z",
            first_detected_at="2026-04-02T09:59:30Z",
            applied_at="2026-04-02T10:00:01Z",
            result=OfferProcessResult.APPLIED,
            reason="Offer applied successfully.",
        )
    )
    repository.save_chat_state(100, state)

    reloaded = P2PMonitorStateStore(tmp_path / "p2p_state.json")
    restored = reloaded.get_chat_state(100)

    assert restored.enabled is True
    assert restored.poll_interval_seconds == 45
    assert restored.target_type == P2POfferType.SELL
    assert restored.rules.coin == "BANK_CUP"
    assert restored.applied_history[0].uuid == "offer-1"
    assert restored.applied_history[0].result == OfferProcessResult.APPLIED


# uv run pytest -s tests/test_p2p_repository.py
def test_repository_can_find_processed_offer(tmp_path: Path) -> None:
    repository = P2PMonitorStateStore(tmp_path / "p2p_state.json")
    state = repository.get_chat_state(1)
    entry = OfferHistoryEntry(
        uuid="offer-2",
        status="open",
        coin="BANK_CUP",
        amount=25,
        receive=6600,
        ratio=264,
        user_uuid="user-2",
        username="bob",
        evaluated_at="2026-04-02T10:05:00Z",
        first_detected_at="2026-04-02T10:04:00Z",
        result=OfferProcessResult.LOST_RACE,
        reason="Offer was taken by another peer first.",
    )
    state.lost_race_history.append(entry)
    repository.save_chat_state(1, state)

    found = repository.find_history_entry(1, "offer-2")

    assert found is not None
    assert found.result == OfferProcessResult.LOST_RACE


# uv run pytest -s tests/test_p2p_repository.py
def test_repository_shares_state_between_chat_ids(tmp_path: Path) -> None:
    repository = P2PMonitorStateStore(tmp_path / "p2p_state.json")

    state_a = repository.get_chat_state(111)
    state_a.enabled = True
    state_a.rules.coin = "BANK_CUP"
    repository.save_chat_state(111, state_a)

    state_b = repository.get_chat_state(222)
    assert state_b.enabled is True
    assert state_b.rules.coin == "BANK_CUP"

    state_b.rules.coin = "ZELLE"
    repository.save_chat_state(222, state_b)

    state_a_after = repository.get_chat_state(111)
    assert state_a_after.rules.coin == "ZELLE"
