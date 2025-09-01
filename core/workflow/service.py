from __future__ import annotations

from typing import List, Optional, Dict

from django.db import transaction
from django.utils.functional import cached_property

from core.models import Order, OrderStatus, OrderTransitionLog
from .types import Transition, TransitionAttempt, TransitionContext, TransitionResult
from .order_workflow import TRANSITIONS, transitions_from_state
from .registry import get_guard, get_effect


class TransitionService:
    """
    Registry-driven workflow executor for Orders.
    - Determines allowed transitions from the current state.
    - Evaluates guards and executes effects.
    - Ensures idempotency and audit logging.
    """

    def __init__(self, transitions: Optional[List[Transition]] = None):
        self._transitions = transitions or TRANSITIONS

    @cached_property
    def _by_to_state(self) -> Dict[str, List[Transition]]:
        by_target: Dict[str, List[Transition]] = {}
        for t in self._transitions:
            by_target.setdefault(t.to_state, []).append(t)
        return by_target

    def transitions_for_state(self, state: str) -> List[Transition]:
        return [t for t in self._transitions if state in t.from_states]

    def allowed_transitions(self, order: Order, ctx: Optional[TransitionContext] = None) -> List[TransitionAttempt]:
        """
        Returns TransitionAttempt entries for transitions from the current state,
        evaluating guards when a context is provided. If ctx is None, guards are not evaluated.
        """
        attempts: List[TransitionAttempt] = []
        for t in self.transitions_for_state(order.status):
            if ctx is None:
                attempts.append(TransitionAttempt(transition=t, allowed=True))
                continue
            ok, reason = self._evaluate_guards(t, ctx)
            attempts.append(TransitionAttempt(transition=t, allowed=ok, reason=reason))
        return attempts

    def can_transition(self, order: Order, to_state: str, ctx: TransitionContext) -> TransitionAttempt:
        t = self._select_transition(order.status, to_state)
        if not t:
            return TransitionAttempt(
                transition=Transition(name=f"to:{to_state}", from_states=[order.status], to_state=to_state),
                allowed=False,
                reason=f"Transition from {order.status} to {to_state} is not defined",
            )
        ok, reason = self._evaluate_guards(t, ctx)
        return TransitionAttempt(transition=t, allowed=ok, reason=reason)

    def transition(
        self,
        order: Order,
        to_state: str,
        *,
        actor_user=None,
        actor_label: str = "",
        note: str = "",
        params: Optional[Dict] = None,
        idempotency_key: Optional[str] = None,
        dry_run: bool = False,
        request=None,
    ) -> TransitionResult:
        """
        Execute a transition to 'to_state' if allowed. Returns a TransitionResult detailing the outcome.
        - Validates existence of a defined transition from the current state.
        - Evaluates guards.
        - On dry_run, does not modify the database.
        - Otherwise updates the order status, executes effects, and writes an audit log.
        - Idempotency: if an audit log with the same idempotency_key exists, returns idempotent=True.
        """
        params = params or {}
        transition_def = self._select_transition(order.status, to_state)
        if not transition_def:
            return TransitionResult(
                success=False,
                from_state=order.status,
                to_state=None,
                errors=[f"No transition defined from {order.status} to {to_state}"],
            )

        ctx = TransitionContext(
            order=order,
            actor_user=actor_user,
            actor_label=actor_label,
            note=note,
            params=params,
            idempotency_key=idempotency_key,
            dry_run=dry_run,
            request=request,
        )

        ok, reason = self._evaluate_guards(transition_def, ctx)
        if not ok:
            return TransitionResult(
                success=False,
                from_state=order.status,
                to_state=None,
                errors=[reason or "Transition blocked by guard"],
            )

        if dry_run:
            return TransitionResult(
                success=True,
                from_state=order.status,
                to_state=to_state,
                messages=[f"Dry-run OK: {order.status} → {to_state} via {transition_def.name}"],
            )

        with transaction.atomic():
            # Lock current row to avoid concurrent state changes
            locked = Order.objects.select_for_update().get(pk=order.pk)

            # Idempotency check
            if idempotency_key:
                existing = OrderTransitionLog.objects.filter(
                    order=locked, idempotency_key=idempotency_key
                ).only("id", "from_state", "to_state")
                if existing.exists():
                    log = existing.first()
                    return TransitionResult(
                        success=True,
                        from_state=log.from_state,
                        to_state=log.to_state,
                        idempotent=True,
                        messages=["Idempotent replay"],
                        log_id=log.id,
                    )

            # Validate still allowed from the latest state
            latest_transition_def = self._select_transition(locked.status, to_state)
            if not latest_transition_def:
                return TransitionResult(
                    success=False,
                    from_state=locked.status,
                    to_state=None,
                    errors=[f"State changed concurrently; {locked.status} → {to_state} not allowed"],
                )

            # Save status change
            prev_state = locked.status
            locked.status = to_state
            locked.save(update_fields=["status", "updated_at"])

            # Run effects (must be idempotent/safe to retry)
            effect_msgs: List[str] = []
            for effect_key in latest_transition_def.effects:
                effect = get_effect(effect_key)
                ctx_locked = TransitionContext(
                    order=locked,
                    actor_user=actor_user,
                    actor_label=actor_label,
                    note=note,
                    params=params,
                    idempotency_key=idempotency_key,
                    dry_run=False,
                    request=request,
                )
                effect(ctx_locked)
                effect_msgs.append(f"effect:{effect_key}:ok")

            # Write audit log
            log = OrderTransitionLog.objects.create(
                order=locked,
                from_state=prev_state,
                to_state=to_state,
                actor_user=actor_user if getattr(actor_user, "is_authenticated", False) else None,
                actor_label=actor_label or (getattr(actor_user, "get_username", lambda: "")() if actor_user else ""),
                note=note,
                metadata={"transition": latest_transition_def.name, "params": params, "effects": effect_msgs},
                idempotency_key=idempotency_key,
            )

            return TransitionResult(
                success=True,
                from_state=prev_state,
                to_state=to_state,
                messages=[f"{prev_state} → {to_state} via {latest_transition_def.name}"] + effect_msgs,
                log_id=log.id,
            )

    # Internal helpers

    def _select_transition(self, from_state: str, to_state: str) -> Optional[Transition]:
        for t in self._transitions:
            if to_state == t.to_state and from_state in t.from_states:
                return t
        return None

    def _evaluate_guards(self, transition_def: Transition, ctx: TransitionContext) -> (bool, Optional[str]):
        for guard_key in transition_def.guards:
            guard = get_guard(guard_key)
            ok, reason = guard(ctx)
            if not ok:
                return False, reason or f"Guard failed: {guard_key}"
        return True, None