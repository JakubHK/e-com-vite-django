# Order Workflow (Short‑term, Registry‑Driven)

This document describes the short‑term flexible workflow for Orders. It is registry‑driven (Option B) with guard/effect plug‑ins and an admin bulk action.

Summary
- Canonical state map:
  - pending → paid → shipped → fulfilled
  - cancel from pending/paid → cancelled
  - refund from fulfilled → refunded
  - return from fulfilled → returned
- Guards validate a transition request (ex: permission checks).
- Effects run side effects (ex: emails, stock ops). Stubs are provided for safe rollout.
- An append‑only audit log records every transition.
- Idempotency keys avoid executing the same transition twice.
- Admin “Apply workflow transition…” bulk action with optional dry‑run.

Key files
- Engine
  - docs/WORKFLOW.md (this guide)
  - core/workflow/types.py
  - core/workflow/registry.py
  - core/workflow/order_workflow.py
  - core/workflow/service.py
- Data models
  - core/models.py (OrderStatus, OrderTransitionLog)
- Admin integration
  - core/admin.py
  - templates/admin/core/order/apply_transition.html
- Feature flag
  - ecom/settings.py (WORKFLOW_ENABLED)

States
- pending (default)
- paid
- shipped
- fulfilled
- cancelled
- refunded
- returned

Transition map
- mark_paid: pending → paid
- ship: paid → shipped
- fulfill: shipped → fulfilled
- cancel: pending/paid → cancelled
- refund: fulfilled → refunded
- return: fulfilled → returned

Guards (built‑in stubs)
- payment_authorized: returns True (wire to real PSP later)
- inventory_available: returns True (wire to stock service later)
- role_allowed: requires an authenticated user with perms (defaults to core.change_order or what you pass as params.required_perms)

Effects (built‑in stubs)
- capture_payment: no‑op (future PSP integration)
- refund_payment: no‑op (future PSP integration)
- reserve_inventory: no‑op (future stock integration)
- release_inventory: no‑op (future stock integration)
- send_email: no‑op (future email integration)
- emit_webhook: no‑op (future webhook dispatcher)

Audit log
- Model: OrderTransitionLog (append‑only)
  - Fields: order, from_state, to_state, actor_user, actor_label, note, metadata (JSON), idempotency_key, created_at
  - Indexed by order and created_at
- Each successful transition writes a new log row with metadata including the transition name and effects executed.

Idempotency
- Pass a unique idempotency_key when executing transitions that may be retried.
- If a previous log exists with the same key, the service responds idempotent=True and returns the previous result.

Feature flag
- WORKFLOW_ENABLED (default True)
  - When True, admin actions use the workflow TransitionService.
  - When False, admin actions fall back to legacy direct status updates (best‑effort compatibility).

Admin usage
- In Orders list:
  - Select orders → Actions → “Apply workflow transition…”
  - Pick a target state, add an optional note, enable “Dry run” if you only want to validate guards.
  - Submit to receive a result message with success/failure counts.
- Convenience actions:
  - “Mark selected orders as Paid” and “Mark selected orders as Cancelled” route through the workflow when enabled (or legacy update when disabled).
- Order detail includes a read‑only “Transitions” inline table showing the audit trail (timestamp, from → to, actor, note).

Extending workflow
- Add a new transition:
  1) Edit core/workflow/order_workflow.py and append a Transition entry to TRANSITIONS.
  2) Attach guards/effects by their registry keys (see “Registering guards/effects”).
  3) Optionally add a convenience admin action that routes to the service.

- Registering guards/effects:
  - In core/workflow/registry.py, use register_guard("key", callable) or register_effect("key", callable).
  - A guard returns (bool, reason_or_None).
  - An effect takes a TransitionContext and returns None (must be idempotent).

- Dotted‑path loading:
  - You can implement a guard/effect elsewhere and load it dynamically using load_dotted_path("package.module.fn"). Then register under your desired key.

Service API (Python)
- TransitionService.transitions_for_state(state) -> list[Transition]
- TransitionService.allowed_transitions(order, ctx?) -> list[TransitionAttempt]
- TransitionService.can_transition(order, to_state, ctx) -> TransitionAttempt
- TransitionService.transition(order, to_state, actor_user=None, actor_label="", note="", params=None, idempotency_key=None, dry_run=False, request=None) -> TransitionResult

Safety, concurrency and transactions
- The service uses select_for_update to lock the Order row during execution.
- Guard checks are re‑checked after locking to avoid races.
- Effects must be idempotent and safe to retry. Stubs are no‑ops for now.
- Failures in effects should raise exceptions to abort the transaction; the transition is then not persisted.

Rollout plan
1) Ship with WORKFLOW_ENABLED=True on development/staging.
2) Verify admin “Apply workflow transition…” flows:
   - Dry run and real transitions across pending → paid → shipped → fulfilled.
   - Cancel from pending/paid; refund/return from fulfilled.
   - Audit log rows populate as expected.
3) Confirm old convenience actions (mark paid/cancelled) work identically.
4) Enable in production behind the feature flag; set to False for emergency fallback.
5) Integrate real systems gradually (PSP, inventory, email, webhooks) by replacing stubs with real effects/guards.
6) Add unit tests (see below).

Testing suggestions
- Create orders in different states and assert:
  - allowed_transitions lists expected targets.
  - can_transition passes/fails on guards as expected (role_allowed depends on user perms).
  - transition(dry_run=True) does not alter DB, returns success.
  - transition() updates status and writes OrderTransitionLog row.
  - Idempotency repeats return idempotent=True without duplicate side effects/logs.
- Admin:
  - Bulk apply a transition with dry run and real execution; check messages and audit lines.

FAQ
- Why not DB‑defined workflows now?
  - The registry approach offers flexibility with much lower complexity. We can later move definitions to DB while reusing the same guard/effect registries and service.
- Can customers trigger transitions on the storefront?
  - Yes. Render allowed actions server‑side and post with HTMX to a server endpoint that validates guards via the service and returns updated fragments. Keep the admin separate.
