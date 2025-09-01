from __future__ import annotations

from typing import List, Dict

from core.models import OrderStatus
from .types import Transition


# Canonical short-term workflow (Option B, registry-driven)
# - pending → paid → shipped → fulfilled
# - cancel from pending/paid → cancelled
# - refund from fulfilled → refunded
# - return from fulfilled → returned
TRANSITIONS: List[Transition] = [
    Transition(
        name="mark_paid",
        from_states=[OrderStatus.PENDING],
        to_state=OrderStatus.PAID,
        guards=["role_allowed", "payment_authorized"],
        effects=["capture_payment", "reserve_inventory", "send_email", "emit_webhook"],
        description="Mark order as paid (captures authorized payment, reserves inventory).",
    ),
    Transition(
        name="ship",
        from_states=[OrderStatus.PAID],
        to_state=OrderStatus.SHIPPED,
        guards=["role_allowed", "inventory_available"],
        effects=["send_email", "emit_webhook"],
        description="Mark order as shipped (notify customer).",
    ),
    Transition(
        name="fulfill",
        from_states=[OrderStatus.SHIPPED],
        to_state=OrderStatus.FULFILLED,
        guards=["role_allowed"],
        effects=["send_email", "emit_webhook"],
        description="Mark order as fulfilled (delivered/complete).",
    ),
    Transition(
        name="cancel",
        from_states=[OrderStatus.PENDING, OrderStatus.PAID],
        to_state=OrderStatus.CANCELLED,
        guards=["role_allowed"],
        effects=["release_inventory", "send_email", "emit_webhook"],
        description="Cancel order (release inventory; external refunds can be handled separately).",
    ),
    Transition(
        name="refund",
        from_states=[OrderStatus.FULFILLED],
        to_state=OrderStatus.REFUNDED,
        guards=["role_allowed"],
        effects=["refund_payment", "release_inventory", "send_email", "emit_webhook"],
        description="Refund order after fulfillment (may be partial based on params).",
    ),
    Transition(
        name="return",
        from_states=[OrderStatus.FULFILLED],
        to_state=OrderStatus.RETURNED,
        guards=["role_allowed"],
        effects=["release_inventory", "send_email", "emit_webhook"],
        description="Mark order as returned (stock operations handled by effect).",
    ),
]


# Helpers

def transitions_by_to_state() -> Dict[str, List[Transition]]:
    by_target: Dict[str, List[Transition]] = {}
    for t in TRANSITIONS:
        by_target.setdefault(t.to_state, []).append(t)
    return by_target


def transitions_from_state(state: str) -> List[Transition]:
    return [t for t in TRANSITIONS if state in t.from_states]