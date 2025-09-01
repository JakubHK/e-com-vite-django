from __future__ import annotations

import importlib
from typing import Any, Callable, Dict, Optional, Tuple

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ImproperlyConfigured

from .types import Guard, Effect, TransitionContext


# In-memory registries for guards and effects
_GUARDS: Dict[str, Guard] = {}
_EFFECTS: Dict[str, Effect] = {}


def register_guard(key: str, fn: Guard) -> None:
    if key in _GUARDS:
        raise ImproperlyConfigured(f"Guard already registered: {key}")
    _GUARDS[key] = fn


def get_guard(key: str) -> Guard:
    try:
        return _GUARDS[key]
    except KeyError:
        raise ImproperlyConfigured(f"Unknown guard: {key}")


def register_effect(key: str, fn: Effect) -> None:
    if key in _EFFECTS:
        raise ImproperlyConfigured(f"Effect already registered: {key}")
    _EFFECTS[key] = fn


def get_effect(key: str) -> Effect:
    try:
        return _EFFECTS[key]
    except KeyError:
        raise ImproperlyConfigured(f"Unknown effect: {key}")


def load_dotted_path(dotted: str) -> Any:
    """
    Load a dotted-path callable, e.g. "core.payments.capture_payment".
    """
    try:
        module_path, attr = dotted.rsplit(".", 1)
        module = importlib.import_module(module_path)
        return getattr(module, attr)
    except Exception as exc:
        raise ImproperlyConfigured(f"Could not import '{dotted}': {exc}") from exc


# Built-in guards (lightweight, safe defaults)

def guard_payment_authorized(ctx: TransitionContext) -> Tuple[bool, Optional[str]]:
    """
    Stub: allow transition; a real implementation would verify payment intent status.
    """
    return True, None


def guard_inventory_available(ctx: TransitionContext) -> Tuple[bool, Optional[str]]:
    """
    Stub: allow transition; a real implementation would check/lock stock reservations.
    """
    return True, None


def guard_role_allowed(ctx: TransitionContext) -> Tuple[bool, Optional[str]]:
    """
    Enforce that an authenticated user with proper perms executes sensitive transitions.
    Uses ctx.params.get("required_perms", [...]) or defaults to ["core.change_order"].
    """
    required = ctx.params.get("required_perms") or ["core.change_order"]
    user = ctx.actor_user
    if not user or isinstance(user, AnonymousUser):
        return False, "Authentication required"
    for perm in required:
        if not user.has_perm(perm):
            return False, f"Missing permission: {perm}"
    return True, None


# Built-in effects (no-ops, safe to call multiple times)

def effect_capture_payment(ctx: TransitionContext) -> None:
    """
    Stub: capture authorized payment for the order.
    """
    # TODO: integrate payment provider here
    return


def effect_refund_payment(ctx: TransitionContext) -> None:
    """
    Stub: refund part or all of a payment based on ctx.params.
    """
    # TODO: integrate payment provider here
    return


def effect_reserve_inventory(ctx: TransitionContext) -> None:
    """
    Stub: reserve stock for all items in the order.
    """
    # TODO: integrate inventory service here
    return


def effect_release_inventory(ctx: TransitionContext) -> None:
    """
    Stub: release any reserved stock (on cancel/return).
    """
    # TODO: integrate inventory service here
    return


def effect_send_email(ctx: TransitionContext) -> None:
    """
    Stub: send transactional email on transition (e.g., order shipped).
    """
    # TODO: integrate email service here
    return


def effect_emit_webhook(ctx: TransitionContext) -> None:
    """
    Stub: emit a webhook event for downstream systems.
    """
    # TODO: integrate webhook dispatcher here
    return


# Register built-ins
register_guard("payment_authorized", guard_payment_authorized)
register_guard("inventory_available", guard_inventory_available)
register_guard("role_allowed", guard_role_allowed)

register_effect("capture_payment", effect_capture_payment)
register_effect("refund_payment", effect_refund_payment)
register_effect("reserve_inventory", effect_reserve_inventory)
register_effect("release_inventory", effect_release_inventory)
register_effect("send_email", effect_send_email)
register_effect("emit_webhook", effect_emit_webhook)