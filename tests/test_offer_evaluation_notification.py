from __future__ import annotations

from qvapay_bot.p2p_formatter import format_offer_evaluation
from qvapay_bot.p2p_models import (
    OfferEvaluation,
    P2PAdvertiser,
    P2POfferSnapshot,
    P2POfferType,
)


# uv run pytest -s tests/test_offer_evaluation_notification.py
def test_format_offer_evaluation_shows_eligible_status() -> None:
    offer = P2POfferSnapshot(
        uuid="uuid-123",
        offer_type=P2POfferType.BUY,
        coin="BANK_CUP",
        amount=100.0,
        receive=26800.0,
        ratio=268.0,
        status="open",
        only_kyc=False,
        only_vip=False,
        created_at="2026-05-09T10:00:00Z",
        advertiser=P2PAdvertiser(
            uuid="adv-1", username="bob", kyc=True, vip=False
        ),
    )
    evaluation = OfferEvaluation(offer=offer, is_eligible=True, reasons=[])

    result = format_offer_evaluation(evaluation)

    assert "✅ elegible" in result
    assert "COMPRA" in result
    assert "BANK_CUP" in result
    assert "100.00" in result
    assert "268" in result


# uv run pytest -s tests/test_offer_evaluation_notification.py
def test_format_offer_evaluation_shows_rejection_reasons() -> None:
    offer = P2POfferSnapshot(
        uuid="uuid-456",
        offer_type=P2POfferType.SELL,
        coin="ZELLE",
        amount=50.0,
        receive=5000.0,
        ratio=100.0,
        status="open",
        only_kyc=False,
        only_vip=False,
        created_at="2026-05-09T10:00:00Z",
        advertiser=P2PAdvertiser(
            uuid="adv-2", username="alice", kyc=False, vip=False
        ),
    )
    evaluation = OfferEvaluation(
        offer=offer,
        is_eligible=False,
        reasons=["ratio<150", "advertiser_without_kyc"],
    )

    result = format_offer_evaluation(evaluation)

    assert "❌ descartada" in result
    assert "ratio<150, advertiser_without_kyc" in result
    assert "VENTA" in result
    assert "ZELLE" in result
    assert "50.00" in result
