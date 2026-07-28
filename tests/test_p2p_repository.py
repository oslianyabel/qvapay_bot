from __future__ import annotations

from pathlib import Path

from qvapay_bot.p2p_models import OfferHistoryEntry, OfferProcessResult, P2POfferType
from qvapay_bot.p2p_repository import P2PMonitorStateStore

USER = "user-1"


def test_repository_persists_monitor_state(tmp_path: Path) -> None:
    repository = P2PMonitorStateStore(tmp_path / "p2p_state.json")

    monitor = repository.create_monitor(USER, "Principal")
    monitor.enabled = True
    monitor.poll_interval_seconds = 45
    monitor.target_type = P2POfferType.SELL
    monitor.rules.coin = "BANK_CUP"
    monitor.applied_history.append(
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
    repository.save_monitor(USER, monitor)

    reloaded = P2PMonitorStateStore(tmp_path / "p2p_state.json")
    restored = reloaded.get_monitor(USER, monitor.id)

    assert restored is not None
    assert restored.name == "Principal"
    assert restored.enabled is True
    assert restored.poll_interval_seconds == 45
    assert restored.target_type == P2POfferType.SELL
    assert restored.rules.coin == "BANK_CUP"
    assert restored.applied_history[0].uuid == "offer-1"
    assert restored.applied_history[0].result == OfferProcessResult.APPLIED


def test_repository_can_find_processed_offer(tmp_path: Path) -> None:
    repository = P2PMonitorStateStore(tmp_path / "p2p_state.json")
    monitor = repository.create_monitor(USER, "Principal")
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
    monitor.lost_race_history.append(entry)
    repository.save_monitor(USER, monitor)

    found = repository.find_history_entry(USER, monitor.id, "offer-2")

    assert found is not None
    assert found.result == OfferProcessResult.LOST_RACE


def test_repository_migrates_v1_state(tmp_path: Path) -> None:
    # Estado v1: {"version":1, "chats": {user_id: {...monitor...}}}
    v1 = (
        '{"version": 1, "chats": {"' + USER + '": '
        '{"enabled": true, "poll_interval_seconds": 30, "target_type": "buy", '
        '"rules": {"coin": "MLC"}}}}'
    )
    path = tmp_path / "p2p_state.json"
    path.write_text(v1, encoding="utf-8")

    repository = P2PMonitorStateStore(path)
    monitors = repository.list_monitors(USER)
    assert len(monitors) == 1
    assert monitors[0].name == "Principal"
    assert monitors[0].enabled is True
    assert monitors[0].target_type == P2POfferType.BUY
    assert monitors[0].rules.coin == "MLC"
    assert monitors[0].id  # se generó un id
