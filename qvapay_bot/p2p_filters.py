from __future__ import annotations

import json
from collections import Counter
from typing import Any

from qvapay_bot.p2p_models import (
    PROCESSED_OFFER_COOLDOWN_SECONDS,
    OfferEvaluation,
    P2PAdvertiser,
    P2PMonitorRules,
    P2POfferSnapshot,
    P2POfferType,
    SelectionStrategy,
    normalize_bool,
    parse_iso_datetime,
)
from qvapay_bot.qvapay_client import LIST_P2P_COIN_ALIASES


def extract_offer_list(body: Any) -> list[Any] | None:
    """Extrae la lista de ofertas de la respuesta de /p2p tolerando variantes:
    array directo, `{"data": [...]}`, `{"offers": [...]}`, paginación anidada
    (`{"data": {"data": [...]}}`) o el cuerpo como string JSON."""
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            return None
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        for key in ("data", "offers", "results"):
            value = body.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict) and isinstance(value.get("data"), list):
                return value["data"]
    return None


def build_offer_snapshot(raw_offer: Any) -> P2POfferSnapshot | None:
    if not isinstance(raw_offer, dict):
        return None

    uuid = str(raw_offer.get("uuid", "")).strip()
    offer_type_raw = str(raw_offer.get("type", "")).strip().lower()
    coin = str(raw_offer.get("coin", "")).strip().upper()
    amount = _to_float(raw_offer.get("amount"))
    receive = _to_float(raw_offer.get("receive"))
    status = str(raw_offer.get("status", "")).strip().lower()
    if not uuid or offer_type_raw not in {"buy", "sell"}:
        return None
    if not coin or amount is None or receive is None or amount <= 0:
        return None

    advertiser_raw = raw_offer.get("User")
    advertiser = P2PAdvertiser(
        uuid=_optional_str(advertiser_raw, "uuid"),
        username=_optional_str(advertiser_raw, "username"),
        kyc=normalize_bool(_optional_value(advertiser_raw, "kyc")),
        vip=normalize_bool(_optional_value(advertiser_raw, "vip")),
    )
    return P2POfferSnapshot(
        uuid=uuid,
        offer_type=P2POfferType(offer_type_raw),
        coin=coin,
        amount=amount,
        receive=receive,
        ratio=receive / amount,
        status=status,
        only_kyc=normalize_bool(raw_offer.get("only_kyc")),
        only_vip=normalize_bool(raw_offer.get("only_vip")),
        created_at=_optional_str(raw_offer, "created_at"),
        advertiser=advertiser,
    )


def evaluate_offer(
    offer: P2POfferSnapshot,
    rules: P2PMonitorRules,
    *,
    target_type: P2POfferType,
    current_user_uuid: str | None,
    processed_offer_timestamps: dict[str, str],
    cooldown_seconds: int = PROCESSED_OFFER_COOLDOWN_SECONDS,
) -> OfferEvaluation:
    reasons: list[str] = []
    if offer.status != "open":
        reasons.append(f"status={offer.status}")

    if target_type != P2POfferType.ANY and offer.offer_type != target_type:
        reasons.append(f"type={offer.offer_type.value}")

    if rules.coin and not _matches_coin_filter(offer.coin, rules.coin):
        reasons.append(f"coin={offer.coin}")

    if rules.min_ratio is not None and offer.ratio < rules.min_ratio:
        reasons.append(f"ratio<{rules.min_ratio}")

    if rules.max_ratio is not None and offer.ratio > rules.max_ratio:
        reasons.append(f"ratio>{rules.max_ratio}")

    if rules.min_amount is not None and offer.amount < rules.min_amount:
        reasons.append(f"amount<{rules.min_amount}")

    if rules.max_amount is not None and offer.amount > rules.max_amount:
        reasons.append(f"amount>{rules.max_amount}")

    if rules.only_kyc and not offer.advertiser.kyc:
        reasons.append("advertiser_without_kyc")

    if rules.only_vip and not offer.advertiser.vip:
        reasons.append("advertiser_without_vip")

    if current_user_uuid and offer.advertiser.uuid == current_user_uuid:
        reasons.append("own_offer")

    processed_at = parse_iso_datetime(processed_offer_timestamps.get(offer.uuid))
    created_at = parse_iso_datetime(offer.created_at)
    if processed_at is not None:
        reference = created_at or processed_at
        age_seconds = (processed_at - reference).total_seconds()
        if age_seconds <= cooldown_seconds:
            reasons.append("processed_recently")

    return OfferEvaluation(offer=offer, is_eligible=not reasons, reasons=reasons)


def sort_eligible_offers(
    evaluations: list[OfferEvaluation],
    rules: P2PMonitorRules,
    strategy: SelectionStrategy = SelectionStrategy.BEST_RATIO,
) -> list[P2POfferSnapshot]:
    eligible_offers = [
        evaluation.offer for evaluation in evaluations if evaluation.is_eligible
    ]
    return sorted(eligible_offers, key=_sort_key_for(strategy, rules))


def _sort_key_for(strategy: SelectionStrategy, rules: P2PMonitorRules):
    """Devuelve la función clave de ordenación (menor = mayor prioridad)."""
    created = _created_at_sort_value

    if strategy == SelectionStrategy.AMOUNT_HIGH:
        return lambda o: (-o.amount, -o.ratio, created(o.created_at))
    if strategy == SelectionStrategy.AMOUNT_LOW:
        return lambda o: (o.amount, -o.ratio, created(o.created_at))
    if strategy == SelectionStrategy.OLDEST:
        return lambda o: (created(o.created_at), -o.ratio)
    if strategy == SelectionStrategy.NEWEST:
        return lambda o: (-created(o.created_at), -o.ratio)
    # BEST_RATIO (por defecto): mejor ratio, luego cercanía al centro del rango, luego antigüedad
    return lambda o: (-o.ratio, _amount_distance(o.amount, rules), created(o.created_at))


def summarize_discarded_reasons(
    evaluations: list[OfferEvaluation],
    *,
    limit: int = 5,
) -> list[str]:
    counter: Counter[str] = Counter()
    for evaluation in evaluations:
        if evaluation.is_eligible:
            continue
        for reason in evaluation.reasons:
            counter[reason] += 1

    return [f"{reason} ({count})" for reason, count in counter.most_common(limit)]


def _matches_coin_filter(offer_coin: str, requested_coin: str) -> bool:
    normalized_requested = requested_coin.strip().upper()
    aliases = LIST_P2P_COIN_ALIASES.get(normalized_requested, (normalized_requested,))
    return offer_coin in aliases


def _amount_distance(amount: float, rules: P2PMonitorRules) -> float:
    if rules.min_amount is None or rules.max_amount is None:
        return 0.0
    center = (rules.min_amount + rules.max_amount) / 2
    return abs(amount - center)


def _created_at_sort_value(value: str | None) -> float:
    parsed = parse_iso_datetime(value)
    return parsed.timestamp() if parsed is not None else 0.0


def _to_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _optional_str(raw_value: Any, field_name: str) -> str | None:
    if not isinstance(raw_value, dict):
        return None
    value = raw_value.get(field_name)
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _optional_value(raw_value: Any, field_name: str) -> Any:
    if not isinstance(raw_value, dict):
        return None
    return raw_value.get(field_name)
