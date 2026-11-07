"""Domain models kept separate from UCP/AP2 wire models."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


LegKind = Literal["flight_out", "hotel", "flight_return"]


@dataclass(frozen=True)
class ItineraryManifest:
    itinerary_id: str
    currency: str
    budget_minor: int
    allowed_merchants: tuple[str, ...]
    outbound_origin: str
    outbound_destination: str
    outbound_arrival: str
    hotel_city: str
    hotel_checkin: str
    hotel_checkout: str
    return_origin: str
    return_destination: str
    return_departure: str
    refundable_required: bool = True

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class BookingFact:
    itinerary_id: str
    transaction_id: str
    checkout_id: str
    leg: LegKind
    merchant_id: str
    merchant_name: str
    item_id: str
    title: str
    amount_minor: int
    currency: str
    origin: str | None = None
    destination: str | None = None
    start: str | None = None
    end: str | None = None
    city: str | None = None
    refundable: bool = True

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Decision:
    permitted: bool
    reason: str
    evidence_commitment: str | None = None

