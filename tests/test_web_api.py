from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from qvapay_bot.http_client import HttpResponse
from qvapay_bot.notifier import NullNotifier
from qvapay_bot.p2p_monitor import P2PMonitorManager
from qvapay_bot.p2p_repository import P2PMonitorStateStore
from qvapay_bot.state import BotStateStore, ChatAuthState

USER_ID = "user-uuid-abc"


class FakeQvaPayClient:
    async def execute(
        self,
        spec: Any,
        arguments: dict[str, Any],
        auth_state: ChatAuthState,
        *,
        photo: Any = None,
    ) -> HttpResponse:
        command = spec.command
        if command == "login":
            if arguments.get("password") == "good":
                return HttpResponse(200, {}, {"accessToken": "bearer-xyz"})
            return HttpResponse(401, {}, {"message": "invalid"})
        if command == "profile":
            return HttpResponse(
                200,
                {},
                {
                    "uuid": USER_ID,
                    "username": "tester",
                    "kyc": True,
                    "p2p_enabled": True,
                    "balance": 42.5,
                },
            )
        if command == "average":
            return HttpResponse(
                200,
                {},
                {"CUP": {"name": "CUP", "average": 400.0, "average_buy": 405.0}},
            )
        if command == "list_p2p":
            return HttpResponse(200, {}, {"data": []})
        raise AssertionError(f"unexpected command {command}")


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    os.environ["JWT_SECRET"] = "test-secret"
    os.environ["BOT_STATE_FILE"] = str(tmp_path / "bot.json")
    os.environ["BOT_P2P_STATE_FILE"] = str(tmp_path / "p2p.json")

    from qvapay_web.app import create_app
    from qvapay_web.deps import (
        get_manager,
        get_qvapay_client,
        get_repository,
        get_state_store,
    )

    state_store = BotStateStore(tmp_path / "bot.json")
    repository = P2PMonitorStateStore(tmp_path / "p2p.json")
    fake_client = FakeQvaPayClient()
    manager = P2PMonitorManager(
        state_store=state_store,
        repository=repository,
        qvapay_client=fake_client,  # type: ignore[arg-type]
        notifier=NullNotifier(),
    )

    app = create_app()
    app.dependency_overrides[get_qvapay_client] = lambda: fake_client
    app.dependency_overrides[get_state_store] = lambda: state_store
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_manager] = lambda: manager

    with TestClient(app) as test_client:
        yield test_client


def _login(client: TestClient) -> None:
    resp = client.post(
        "/api/auth/login",
        json={"email": "a@b.com", "password": "good"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["uuid"] == USER_ID


def _create_monitor(client: TestClient, name: str = "M1") -> str:
    resp = client.post("/api/monitors", json={"name": name})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == name
    assert body["id"]
    return body["id"]


def test_requires_auth(client: TestClient) -> None:
    assert client.get("/api/monitors").status_code == 401


def test_login_bad_credentials(client: TestClient) -> None:
    resp = client.post(
        "/api/auth/login", json={"email": "a@b.com", "password": "wrong"}
    )
    assert resp.status_code == 401


def test_create_and_list_multiple_monitors(client: TestClient) -> None:
    _login(client)

    listing = client.get("/api/monitors")
    assert listing.status_code == 200
    assert listing.json()["monitors"] == []
    assert listing.json()["balance"] == 42.5

    id1 = _create_monitor(client, "Uno")
    id2 = _create_monitor(client, "Dos")
    assert id1 != id2

    listing = client.get("/api/monitors")
    ids = {m["id"] for m in listing.json()["monitors"]}
    assert ids == {id1, id2}


def test_rules_update_and_start_stop(client: TestClient) -> None:
    _login(client)
    monitor_id = _create_monitor(client)

    rules = client.put(
        f"/api/monitors/{monitor_id}/rules",
        json={
            "name": "Renombrado",
            "target_type": "sell",
            "poll_interval_seconds": 10,
            "coin": "cup",
            "min_ratio": 300,
            "max_ratio": 500,
        },
    )
    assert rules.status_code == 200, rules.text
    data = rules.json()
    assert data["name"] == "Renombrado"
    assert data["rules"]["coin"] == "CUP"
    assert data["poll_interval_seconds"] == 10

    started = client.post(f"/api/monitors/{monitor_id}/start")
    assert started.status_code == 200
    assert started.json()["enabled"] is True

    stopped = client.post(f"/api/monitors/{monitor_id}/stop")
    assert stopped.status_code == 200
    assert stopped.json()["enabled"] is False


def test_rules_validation(client: TestClient) -> None:
    _login(client)
    monitor_id = _create_monitor(client)
    resp = client.put(
        f"/api/monitors/{monitor_id}/rules",
        json={"min_ratio": 500, "max_ratio": 100},
    )
    assert resp.status_code == 422


def test_delete_monitor(client: TestClient) -> None:
    _login(client)
    monitor_id = _create_monitor(client)
    assert client.delete(f"/api/monitors/{monitor_id}").status_code == 200
    assert client.get("/api/monitors").json()["monitors"] == []


def test_coins_endpoint(client: TestClient) -> None:
    _login(client)
    resp = client.get("/api/coins")
    assert resp.status_code == 200
    coins = resp.json()["coins"]
    assert "CUP" in coins
    assert coins["CUP"]["average"] == 400.0
