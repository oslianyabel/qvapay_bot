"""Modelos Pydantic para las peticiones/respuestas de la API web."""

from __future__ import annotations

from pydantic import BaseModel, Field

from qvapay_bot.p2p_models import (
    MIN_P2P_POLL_INTERVAL_SECONDS,
    P2POfferType,
)


class LoginRequest(BaseModel):
    email: str
    password: str
    two_factor_code: str | None = None


class MonitorCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=60)


class RulesUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=60)
    target_type: P2POfferType = P2POfferType.ANY
    poll_interval_seconds: int = Field(
        default=MIN_P2P_POLL_INTERVAL_SECONDS, ge=MIN_P2P_POLL_INTERVAL_SECONDS
    )
    coin: str | None = None
    min_ratio: float | None = Field(default=None, ge=0)
    max_ratio: float | None = Field(default=None, ge=0)
    min_amount: float | None = Field(default=None, gt=0)
    max_amount: float | None = Field(default=None, gt=0)
    only_kyc: bool = False
    only_vip: bool = False
