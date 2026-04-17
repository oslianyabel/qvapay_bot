from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

DEFAULT_P2P_POLL_INTERVAL_SECONDS = 5
MIN_P2P_POLL_INTERVAL_SECONDS = 5
MAX_HISTORY_ITEMS = 25
MAX_SEEN_OFFERS = 100
PROCESSED_OFFER_COOLDOWN_SECONDS = 3600


class P2POfferType(StrEnum):
    BUY = "buy"
    SELL = "sell"
    ANY = "any"


class OfferProcessResult(StrEnum):
    MATCHED = "matched"
    APPLIED = "applied"
    LOST_RACE = "lost_race"
    REJECTED = "rejected"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"


@dataclass(slots=True, frozen=True)
class P2PAdvertiser:
    uuid: str | None
    username: str | None
    kyc: bool
    vip: bool


@dataclass(slots=True, frozen=True)
class P2POfferSnapshot:
    uuid: str
    offer_type: P2POfferType
    coin: str
    amount: float
    receive: float
    ratio: float
    status: str
    only_kyc: bool
    only_vip: bool
    created_at: str | None
    advertiser: P2PAdvertiser


@dataclass(slots=True)
class P2PMonitorRules:
    coin: str | None = None
    min_ratio: float | None = None
    max_ratio: float | None = None
    min_amount: float | None = None
    max_amount: float | None = None
    only_kyc: bool = False
    only_vip: bool = False


@dataclass(slots=True)
class OfferEvaluation:
    offer: P2POfferSnapshot
    is_eligible: bool
    reasons: list[str]


@dataclass(slots=True)
class OfferHistoryEntry:
    uuid: str
    status: str
    coin: str
    amount: float
    receive: float
    ratio: float
    user_uuid: str | None
    username: str | None
    evaluated_at: str
    first_detected_at: str
    notified_at: str | None = None
    applied_at: str | None = None
    result: OfferProcessResult | None = None
    reason: str | None = None


@dataclass(slots=True)
class P2PMonitorChatState:
    enabled: bool = False
    poll_interval_seconds: int = DEFAULT_P2P_POLL_INTERVAL_SECONDS
    target_type: P2POfferType = P2POfferType.ANY
    rules: P2PMonitorRules = field(default_factory=P2PMonitorRules)
    seen_offer_ids: list[str] = field(default_factory=list)
    first_seen_at_by_offer: dict[str, str] = field(default_factory=dict)
    processed_offer_timestamps: dict[str, str] = field(default_factory=dict)
    filtered_history: list[OfferHistoryEntry] = field(default_factory=list)
    discarded_history: list[OfferHistoryEntry] = field(default_factory=list)
    notified_history: list[OfferHistoryEntry] = field(default_factory=list)
    applied_history: list[OfferHistoryEntry] = field(default_factory=list)
    lost_race_history: list[OfferHistoryEntry] = field(default_factory=list)
    last_error: str | None = None
    last_error_at: str | None = None
    last_success_at: str | None = None


@dataclass(slots=True)
class P2PMonitorCycleReport:
    read_count: int = 0
    filtered_count: int = 0
    discarded_count: int = 0
    matched_entry: OfferHistoryEntry | None = None
    final_entry: OfferHistoryEntry | None = None
    top_discarded_reasons: list[str] = field(default_factory=list)
    error_message: str | None = None
    rate_limited: bool = False
    next_sleep_seconds: float | None = None


def utcnow_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def offer_history_from_offer(
    offer: P2POfferSnapshot,
    *,
    evaluated_at: str,
    first_detected_at: str,
    result: OfferProcessResult | None = None,
    reason: str | None = None,
    notified_at: str | None = None,
    applied_at: str | None = None,
) -> OfferHistoryEntry:
    return OfferHistoryEntry(
        uuid=offer.uuid,
        status=offer.status,
        coin=offer.coin,
        amount=offer.amount,
        receive=offer.receive,
        ratio=offer.ratio,
        user_uuid=offer.advertiser.uuid,
        username=offer.advertiser.username,
        evaluated_at=evaluated_at,
        first_detected_at=first_detected_at,
        notified_at=notified_at,
        applied_at=applied_at,
        result=result,
        reason=reason,
    )


def trim_history(entries: list[OfferHistoryEntry]) -> list[OfferHistoryEntry]:
    return entries[:MAX_HISTORY_ITEMS]


def normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        return lowered in {"1", "true", "yes", "on", "si", "y"}
    return False
