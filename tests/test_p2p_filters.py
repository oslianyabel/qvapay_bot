from __future__ import annotations

from qvapay_bot.p2p_filters import (
    build_offer_snapshot,
    evaluate_offer,
    sort_eligible_offers,
)
from qvapay_bot.p2p_models import P2PMonitorRules, P2POfferType


# uv run pytest -s tests/test_p2p_filters.py
def test_build_offer_snapshot_and_evaluate_offer() -> None:
    raw_offer = {
        "uuid": "offer-1",
        "type": "sell",
        "coin": "BANK_CUP",
        "amount": 50,
        "receive": 13500,
        "status": "open",
        "only_kyc": 1,
        "only_vip": 0,
        "created_at": "2026-04-02T10:00:00.000Z",
        "User": {
            "uuid": "user-1",
            "username": "alice",
            "kyc": True,
            "vip": False,
        },
    }

    offer = build_offer_snapshot(raw_offer)

    assert offer is not None
    assert offer.ratio == 270
    rules = P2PMonitorRules(coin="BANK_CUP", min_ratio=260, only_kyc=True)
    evaluation = evaluate_offer(
        offer,
        rules,
        target_type=P2POfferType.SELL,
        current_user_uuid="another-user",
        processed_offer_timestamps={},
    )

    assert evaluation.is_eligible is True
    assert evaluation.reasons == []


# uv run pytest -s tests/test_p2p_filters.py
def test_evaluate_offer_rejects_own_or_recently_processed_offer() -> None:
    offer = build_offer_snapshot(
        {
            "uuid": "offer-2",
            "type": "buy",
            "coin": "BANK_CUP",
            "amount": 10,
            "receive": 2500,
            "status": "open",
            "created_at": "2026-04-02T10:01:00.000Z",
            "User": {"uuid": "self-user", "username": "me", "kyc": True, "vip": True},
        }
    )

    assert offer is not None
    evaluation = evaluate_offer(
        offer,
        P2PMonitorRules(),
        target_type=P2POfferType.ANY,
        current_user_uuid="self-user",
        processed_offer_timestamps={"offer-2": "2026-04-02T10:01:30Z"},
    )

    assert evaluation.is_eligible is False
    assert "own_offer" in evaluation.reasons
    assert "processed_recently" in evaluation.reasons


# uv run pytest -s tests/test_p2p_filters.py
def test_sort_eligible_offers_prioritizes_ratio_then_centered_amount() -> None:
    first = build_offer_snapshot(
        {
            "uuid": "offer-1",
            "type": "sell",
            "coin": "BANK_CUP",
            "amount": 30,
            "receive": 7800,
            "status": "open",
            "created_at": "2026-04-02T10:00:00.000Z",
            "User": {"uuid": "user-1", "username": "a", "kyc": True, "vip": False},
        }
    )
    second = build_offer_snapshot(
        {
            "uuid": "offer-2",
            "type": "sell",
            "coin": "BANK_CUP",
            "amount": 50,
            "receive": 13500,
            "status": "open",
            "created_at": "2026-04-02T10:01:00.000Z",
            "User": {"uuid": "user-2", "username": "b", "kyc": True, "vip": False},
        }
    )
    assert first is not None and second is not None

    rules = P2PMonitorRules(min_amount=40, max_amount=60)
    evaluations = [
        evaluate_offer(
            first,
            rules,
            target_type=P2POfferType.SELL,
            current_user_uuid=None,
            processed_offer_timestamps={},
        ),
        evaluate_offer(
            second,
            rules,
            target_type=P2POfferType.SELL,
            current_user_uuid=None,
            processed_offer_timestamps={},
        ),
    ]

    sorted_offers = sort_eligible_offers(evaluations, rules)

    assert [offer.uuid for offer in sorted_offers] == ["offer-2"]
