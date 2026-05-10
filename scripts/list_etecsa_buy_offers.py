# uv run python -m scripts.list_etecsa_buy_offers
from __future__ import annotations

import asyncio
import os
from typing import Any

from qvapay_bot.config import Settings
from qvapay_bot.http_client import AsyncHttpClient
from qvapay_bot.p2p_filters import build_offer_snapshot, evaluate_offer, sort_eligible_offers
from qvapay_bot.p2p_formatter import QVAPAY_P2P_URL
from qvapay_bot.p2p_models import P2PMonitorRules, P2POfferType
from qvapay_bot.qvapay_client import COMMAND_INDEX, QvaPayClient
from qvapay_bot.state import BotStateStore, ChatAuthState

BOT_CHAT_ID_ENV = "BOT_CHAT_ID"


def _build_list_arguments(
    rules: P2PMonitorRules,
    target_type: P2POfferType,
) -> dict[str, Any]:
    arguments: dict[str, Any] = {
        "page": 1,
        "take": 100,
        "status": "open",
    }
    if target_type != P2POfferType.ANY:
        arguments["type"] = target_type.value
    if rules.coin:
        arguments["coin"] = rules.coin
    return arguments


def _parse_forced_chat_id() -> int | None:
    raw_chat_id = os.getenv(BOT_CHAT_ID_ENV, "").strip()
    if not raw_chat_id:
        return None
    try:
        return int(raw_chat_id)
    except ValueError as exc:
        raise ValueError(f"{BOT_CHAT_ID_ENV} must be a valid integer chat id") from exc


def _resolve_auth_state(
    state_store: BotStateStore,
    forced_chat_id: int | None,
) -> tuple[int, ChatAuthState]:
    if forced_chat_id is not None:
        auth_state = state_store.get_chat_state(forced_chat_id)
        if not auth_state.has_bearer:
            raise ValueError(
                f"Chat {forced_chat_id} does not have a bearer token in state file."
            )
        return forced_chat_id, auth_state

    for chat_id, auth_state in state_store.iter_chat_states():
        if auth_state.has_bearer:
            return chat_id, auth_state

    raise ValueError("No chat with bearer token was found in bot state.")


def _build_rules() -> tuple[P2PMonitorRules, P2POfferType]:
    return (
        P2PMonitorRules(
            coin="ETECSA",
            min_ratio=None,
            max_ratio=255,
            min_amount=None,
            max_amount=None,
            only_kyc=False,
            only_vip=False,
        ),
        P2POfferType.SELL,
    )


async def _run() -> None:
    settings = Settings.from_env()
    state_store = BotStateStore(settings.state_file)

    chat_id, auth_state = _resolve_auth_state(state_store, _parse_forced_chat_id())
    rules, target_type = _build_rules()

    qvapay_client = QvaPayClient(
        AsyncHttpClient(settings.http_timeout_seconds),
        settings.qvapay_base_url,
    )
    response = await qvapay_client.execute(
        COMMAND_INDEX["list_p2p"],
        _build_list_arguments(rules, target_type),
        auth_state,
    )

    if response.status_code >= 400:
        raise RuntimeError(f"Unable to read offers. HTTP {response.status_code}.")

    offers_raw = None
    if isinstance(response.body, dict):
        offers_raw = response.body.get("data") or response.body.get("offers")
    if not isinstance(offers_raw, list):
        raise RuntimeError("Invalid /p2p payload: expected data/offers list.")

    offers = [
        offer
        for item in offers_raw
        if (offer := build_offer_snapshot(item)) is not None
    ]

    evaluations = [
        evaluate_offer(
            offer,
            rules,
            target_type=target_type,
            current_user_uuid=None,
            processed_offer_timestamps={},
        )
        for offer in offers
    ]
    matching_offers = sort_eligible_offers(evaluations, rules)

    print(f"chat_id: {chat_id}")
    print("Estado del filtro aplicado")
    print("activo: yes")
    print("moneda: ETECSA")
    print("tipo_oferta: sell QUSD -> buy ETECSA")
    print("ratio_min: any")
    print("ratio_max: 255")
    print("monto_min: any")
    print("monto_max: any")
    print("solo_kyc: no")
    print("solo_vip: no")
    print()

    print(f"ofertas_leidas: {len(offers)}")
    print(f"ofertas_encontradas: {len(matching_offers)}")

    if not matching_offers:
        print("No matching offers found.")
        return

    for index, offer in enumerate(matching_offers, start=1):
        username = offer.advertiser.username or "unknown"
        link = f"{QVAPAY_P2P_URL}{offer.uuid}"
        print()
        print(f"Oferta #{index}")
        print(f"- UUID: {offer.uuid}")
        print(f"- Usuario: {username}")
        print(f"- Moneda: {offer.coin}")
        print(f"- Monto: {offer.amount:.2f} QUSD")
        print(f"- Recibes: {offer.receive:.2f} {offer.coin}")
        print(f"- Ratio: {offer.ratio:.4f}")
        print(f"- Link: {link}")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
