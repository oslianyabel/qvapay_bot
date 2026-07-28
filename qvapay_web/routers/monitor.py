"""CRUD y control de monitores P2P (múltiples por usuario)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

from qvapay_bot.p2p_models import P2PMonitorChatState, P2PMonitorRules
from qvapay_bot.serialization import cycle_report_to_dict, monitor_state_to_dict
from qvapay_web.deps import CurrentUserDep, ManagerDep, RepositoryDep
from qvapay_web.schemas import MonitorCreateRequest, RulesUpdateRequest

router = APIRouter(prefix="/monitors", tags=["monitors"])


def _view(manager: ManagerDep, user_id: str, monitor: P2PMonitorChatState) -> dict[str, Any]:
    data = monitor_state_to_dict(monitor)
    data["running"] = manager.is_running(user_id, monitor.id)
    return data


def _require_monitor(
    repository: RepositoryDep, user_id: str, monitor_id: str
) -> P2PMonitorChatState:
    monitor = repository.get_monitor(user_id, monitor_id)
    if monitor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Monitor no encontrado."
        )
    return monitor


@router.get("")
async def list_monitors(
    user: CurrentUserDep,
    manager: ManagerDep,
    repository: RepositoryDep,
) -> dict[str, Any]:
    monitors = repository.list_monitors(user.user_id)
    balance = await manager.fetch_balance(user.auth_state)
    return {
        "balance": balance,
        "monitors": [_view(manager, user.user_id, m) for m in monitors],
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_monitor(
    payload: MonitorCreateRequest,
    user: CurrentUserDep,
    manager: ManagerDep,
    repository: RepositoryDep,
) -> dict[str, Any]:
    monitor = repository.create_monitor(user.user_id, payload.name)
    return _view(manager, user.user_id, monitor)


@router.put("/{monitor_id}/rules")
async def update_rules(
    monitor_id: str,
    payload: RulesUpdateRequest,
    user: CurrentUserDep,
    manager: ManagerDep,
    repository: RepositoryDep,
) -> dict[str, Any]:
    if (
        payload.min_ratio is not None
        and payload.max_ratio is not None
        and payload.min_ratio > payload.max_ratio
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="min_ratio no puede ser mayor que max_ratio.",
        )
    if (
        payload.min_amount is not None
        and payload.max_amount is not None
        and payload.min_amount > payload.max_amount
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="min_amount no puede ser mayor que max_amount.",
        )

    monitor = _require_monitor(repository, user.user_id, monitor_id)
    if payload.name is not None and payload.name.strip():
        monitor.name = payload.name.strip()
    monitor.target_type = payload.target_type
    monitor.selection_strategy = payload.selection_strategy
    monitor.apply_mode = payload.apply_mode
    monitor.poll_interval_seconds = payload.poll_interval_seconds
    coin = payload.coin.strip().upper() if payload.coin else None
    monitor.rules = P2PMonitorRules(
        coin=coin or None,
        min_ratio=payload.min_ratio,
        max_ratio=payload.max_ratio,
        min_amount=payload.min_amount,
        max_amount=payload.max_amount,
        only_kyc=payload.only_kyc,
        only_vip=payload.only_vip,
    )
    repository.save_monitor(user.user_id, monitor)

    if monitor.enabled:
        await manager.restart_monitor(user.user_id, monitor_id)

    return _view(manager, user.user_id, monitor)


@router.delete("/{monitor_id}")
async def delete_monitor(
    monitor_id: str,
    user: CurrentUserDep,
    manager: ManagerDep,
    repository: RepositoryDep,
) -> dict[str, bool]:
    _require_monitor(repository, user.user_id, monitor_id)
    await manager.stop_monitor(user.user_id, monitor_id)
    repository.delete_monitor(user.user_id, monitor_id)
    return {"ok": True}


@router.post("/{monitor_id}/start")
async def start_monitor(
    monitor_id: str,
    user: CurrentUserDep,
    manager: ManagerDep,
    repository: RepositoryDep,
) -> dict[str, Any]:
    monitor = _require_monitor(repository, user.user_id, monitor_id)
    monitor.enabled = True
    monitor.last_error = None
    monitor.last_error_at = None
    repository.save_monitor(user.user_id, monitor)
    await manager.restart_monitor(user.user_id, monitor_id)
    return _view(manager, user.user_id, monitor)


@router.post("/{monitor_id}/stop")
async def stop_monitor(
    monitor_id: str,
    user: CurrentUserDep,
    manager: ManagerDep,
    repository: RepositoryDep,
) -> dict[str, Any]:
    monitor = _require_monitor(repository, user.user_id, monitor_id)
    monitor.enabled = False
    repository.save_monitor(user.user_id, monitor)
    await manager.stop_monitor(user.user_id, monitor_id)
    return _view(manager, user.user_id, monitor)


@router.post("/{monitor_id}/test")
async def test_cycle(
    monitor_id: str,
    user: CurrentUserDep,
    manager: ManagerDep,
    repository: RepositoryDep,
) -> dict[str, Any]:
    _require_monitor(repository, user.user_id, monitor_id)
    report = await manager.run_cycle_once(
        user.user_id, monitor_id, user.auth_state, force=True, dry_run=True
    )
    return cycle_report_to_dict(report)
