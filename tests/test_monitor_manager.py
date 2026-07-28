from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from qvapay_bot.http_client import HttpResponse
from qvapay_bot.notifier import EventType, MonitorEvent
from qvapay_bot.p2p_models import (
    OfferProcessResult,
    P2PMonitorRules,
    P2POfferType,
)
from qvapay_bot.p2p_monitor import P2PMonitorManager
from qvapay_bot.p2p_repository import P2PMonitorStateStore
from qvapay_bot.state import BotStateStore, ChatAuthState

USER_ID = "user-uuid-123"


class FakeNotifier:
    def __init__(self) -> None:
        self.events: list[MonitorEvent] = []

    async def emit(self, event: MonitorEvent) -> None:
        self.events.append(event)

    def types(self) -> list[str]:
        return [e.type for e in self.events]


class FakeQvaPayClient:
    def __init__(
        self,
        *,
        offers: list[dict[str, Any]],
        balance: float = 100.0,
        apply_status: int = 201,
    ) -> None:
        self._offers = offers
        self._balance = balance
        self._apply_status = apply_status
        self.applied_uuids: list[str] = []

    async def execute(
        self,
        spec: Any,
        arguments: dict[str, Any],
        auth_state: ChatAuthState,
        *,
        photo: Any = None,
    ) -> HttpResponse:
        command = spec.command
        if command == "profile":
            return HttpResponse(
                status_code=200,
                headers={},
                body={
                    "uuid": USER_ID,
                    "username": "tester",
                    "kyc": True,
                    "p2p_enabled": True,
                    "balance": self._balance,
                },
            )
        if command == "list_p2p":
            return HttpResponse(
                status_code=200, headers={}, body={"data": self._offers}
            )
        if command == "apply_p2p":
            self.applied_uuids.append(str(arguments.get("uuid")))
            return HttpResponse(status_code=self._apply_status, headers={}, body={})
        raise AssertionError(f"unexpected command {command}")


def _offer(uuid: str, *, offer_type: str = "sell") -> dict[str, Any]:
    return {
        "uuid": uuid,
        "type": offer_type,
        "coin": "BANK_CUP",
        "amount": 10.0,
        "receive": 4000.0,
        "status": "open",
        "only_kyc": False,
        "only_vip": False,
        "created_at": "2026-07-26T00:00:00Z",
        "User": {"uuid": "adv-1", "username": "seller", "kyc": True, "vip": False},
    }


def _build(tmp_path: Path, client: FakeQvaPayClient, notifier: FakeNotifier):
    state_store = BotStateStore(tmp_path / "bot.json")
    repository = P2PMonitorStateStore(tmp_path / "p2p.json")
    manager = P2PMonitorManager(
        state_store=state_store,
        repository=repository,
        qvapay_client=client,  # type: ignore[arg-type]
        notifier=notifier,
    )
    return state_store, repository, manager


def _make_monitor(
    repository: P2PMonitorStateStore,
    *,
    target_type: P2POfferType,
    coin: str | None = "CUP",
):
    monitor = repository.create_monitor(USER_ID, "Test")
    monitor.enabled = True
    monitor.target_type = target_type
    monitor.rules = P2PMonitorRules(coin=coin)
    repository.save_monitor(USER_ID, monitor)
    return monitor


def test_cycle_applies_eligible_offer(tmp_path: Path) -> None:
    client = FakeQvaPayClient(offers=[_offer("offer-1")])
    notifier = FakeNotifier()
    state_store, repository, manager = _build(tmp_path, client, notifier)

    auth = ChatAuthState(bearer_token="tok", user_uuid=USER_ID, username="tester")
    state_store.save_chat_state(USER_ID, auth)
    monitor = _make_monitor(repository, target_type=P2POfferType.SELL)

    report = asyncio.run(
        manager.run_cycle_once(USER_ID, monitor.id, auth, force=True)
    )

    assert report.read_count == 1
    assert report.filtered_count == 1
    assert report.selected_offer is not None
    assert report.final_entry is not None
    assert report.final_entry.result == OfferProcessResult.APPLIED
    assert client.applied_uuids == ["offer-1"]
    assert EventType.OFFER_SELECTED in notifier.types()
    assert EventType.APPLY_RESULT in notifier.types()
    # Los eventos incluyen el id del monitor.
    assert all(e.data.get("monitor_id") == monitor.id for e in notifier.events)

    reloaded = repository.get_monitor(USER_ID, monitor.id)
    assert reloaded is not None
    assert reloaded.applied_history
    assert reloaded.applied_history[0].uuid == "offer-1"


def test_dry_run_does_not_apply(tmp_path: Path) -> None:
    client = FakeQvaPayClient(offers=[_offer("offer-2")])
    notifier = FakeNotifier()
    state_store, repository, manager = _build(tmp_path, client, notifier)

    auth = ChatAuthState(bearer_token="tok", user_uuid=USER_ID)
    state_store.save_chat_state(USER_ID, auth)
    monitor = _make_monitor(repository, target_type=P2POfferType.SELL)

    report = asyncio.run(
        manager.run_cycle_once(USER_ID, monitor.id, auth, force=True, dry_run=True)
    )

    assert report.selected_offer is not None
    assert report.final_entry is None
    assert client.applied_uuids == []


def test_buy_stops_when_balance_low(tmp_path: Path) -> None:
    client = FakeQvaPayClient(offers=[_offer("offer-3", offer_type="buy")], balance=0.0)
    notifier = FakeNotifier()
    state_store, repository, manager = _build(tmp_path, client, notifier)

    auth = ChatAuthState(bearer_token="tok", user_uuid=USER_ID)
    state_store.save_chat_state(USER_ID, auth)
    monitor = _make_monitor(repository, target_type=P2POfferType.BUY)

    report = asyncio.run(
        manager.run_cycle_once(USER_ID, monitor.id, auth, force=True)
    )

    assert report.error_message == "Balance too low."
    assert client.applied_uuids == []
    assert EventType.MONITOR_STOPPED in notifier.types()
    reloaded = repository.get_monitor(USER_ID, monitor.id)
    assert reloaded is not None and reloaded.enabled is False


def test_multiple_monitors_are_independent(tmp_path: Path) -> None:
    client = FakeQvaPayClient(offers=[_offer("offer-x")])
    notifier = FakeNotifier()
    state_store, repository, manager = _build(tmp_path, client, notifier)

    m1 = repository.create_monitor(USER_ID, "Uno")
    m2 = repository.create_monitor(USER_ID, "Dos")
    assert m1.id != m2.id
    assert {m.id for m in repository.list_monitors(USER_ID)} == {m1.id, m2.id}

    repository.delete_monitor(USER_ID, m1.id)
    assert [m.id for m in repository.list_monitors(USER_ID)] == [m2.id]
