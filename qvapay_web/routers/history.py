"""Monedas/promedios, saldo, historial y vista previa de ofertas por monitor."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

from qvapay_bot.p2p_filters import build_offer_snapshot, evaluate_offer
from qvapay_bot.qvapay_client import COMMAND_INDEX
from qvapay_bot.serialization import evaluation_to_dict, history_entry_to_dict
from qvapay_web.deps import (
    CurrentUserDep,
    ManagerDep,
    QvaPayClientDep,
    RepositoryDep,
)

router = APIRouter(tags=["data"])


@router.get("/coins")
async def get_coins(
    user: CurrentUserDep,
    qvapay_client: QvaPayClientDep,
) -> dict[str, Any]:
    """Monedas P2P disponibles con su ratio de cambio promedio actual."""
    response = await qvapay_client.execute(
        COMMAND_INDEX["average"], {}, user.auth_state
    )
    coins = response.body if isinstance(response.body, dict) else {}
    return {"coins": coins}


@router.get("/balance")
async def get_balance(user: CurrentUserDep, manager: ManagerDep) -> dict[str, Any]:
    balance = await manager.fetch_balance(user.auth_state)
    return {"balance": balance}


@router.get("/monitors/{monitor_id}/history")
async def get_history(
    monitor_id: str,
    user: CurrentUserDep,
    repository: RepositoryDep,
) -> dict[str, list[dict[str, Any]]]:
    monitor = repository.get_monitor(user.user_id, monitor_id)
    if monitor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Monitor no encontrado."
        )
    return {
        "applied": [history_entry_to_dict(e) for e in monitor.applied_history],
        "lost_race": [history_entry_to_dict(e) for e in monitor.lost_race_history],
        "notified": [history_entry_to_dict(e) for e in monitor.notified_history],
        "filtered": [history_entry_to_dict(e) for e in monitor.filtered_history],
        "discarded": [history_entry_to_dict(e) for e in monitor.discarded_history],
    }


@router.get("/monitors/{monitor_id}/offers")
async def get_offers(
    monitor_id: str,
    user: CurrentUserDep,
    qvapay_client: QvaPayClientDep,
    repository: RepositoryDep,
) -> dict[str, Any]:
    """Vista previa (solo lectura) de las ofertas P2P actuales y su evaluación."""
    monitor = repository.get_monitor(user.user_id, monitor_id)
    if monitor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Monitor no encontrado."
        )
    arguments: dict[str, Any] = {"page": 1, "take": 100, "status": "open"}
    if monitor.rules.coin:
        arguments["coin"] = monitor.rules.coin
    response = await qvapay_client.execute(
        COMMAND_INDEX["list_p2p"], arguments, user.auth_state
    )
    offers_raw = None
    if isinstance(response.body, dict):
        offers_raw = response.body.get("data") or response.body.get("offers")
    if not isinstance(offers_raw, list):
        return {"offers": [], "error": f"HTTP {response.status_code}"}

    offers = [
        offer
        for item in offers_raw
        if (offer := build_offer_snapshot(item)) is not None
    ]
    evaluations = [
        evaluate_offer(
            offer,
            monitor.rules,
            target_type=monitor.target_type,
            current_user_uuid=user.auth_state.user_uuid,
            processed_offer_timestamps=monitor.processed_offer_timestamps,
        )
        for offer in offers
    ]
    return {"offers": [evaluation_to_dict(e) for e in evaluations]}
