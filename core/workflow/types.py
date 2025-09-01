from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple, List, Protocol


# Protocols for guards and effects
class Guard(Protocol):
    def __call__(self, ctx: "TransitionContext") -> Tuple[bool, Optional[str]]:
        ...


class Effect(Protocol):
    def __call__(self, ctx: "TransitionContext") -> None:
        ...


@dataclass(frozen=True)
class Transition:
    """
    Declarative transition definition.
    - name: unique key for the transition (e.g., 'mark_paid', 'ship', 'fulfill')
    - from_states: allowed source states
    - to_state: target state
    - guards/effects: registry keys to evaluate/execute during transition
    - permissions: optional Django perm codes allowing who can execute this transition
    """
    name: str
    from_states: List[str]
    to_state: str
    guards: List[str] = field(default_factory=list)
    effects: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    description: str = ""


@dataclass
class TransitionContext:
    """
    Execution context passed to guards and effects.
    """
    order: Any  # core.models.Order (kept as Any to avoid import cycles)
    actor_user: Any = None  # request.user or system user
    actor_label: str = ""   # fallback display if actor_user is None
    note: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    idempotency_key: Optional[str] = None
    dry_run: bool = False
    request: Any = None


@dataclass
class TransitionAttempt:
    transition: Transition
    allowed: bool
    reason: Optional[str] = None


@dataclass
class TransitionResult:
    """
    Result of executing a transition.
    """
    success: bool
    from_state: str
    to_state: Optional[str] = None
    messages: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    idempotent: bool = False
    log_id: Optional[int] = None
    data: Dict[str, Any] = field(default_factory=dict)