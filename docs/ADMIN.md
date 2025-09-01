# Django Admin Guide

This guide summarizes how to use the Django Admin configured for the e‑commerce project, including catalog management, orders management with workflow transitions, and operational tips.

Quick links
- Admin site: /admin/
- Models: Category, Product, Order (+ inline OrderItem), OrderTransitionLog
- Workflow docs: docs/WORKFLOW.md

Branding
- Admin branding headers and titles are configured for clarity.

Catalog management

Categories
- Create and edit categories under “Categories”.
- Slug is prepopulated from title.
- List view displays Product count for each category and supports searching and ordering.

Products
- Create and edit products under “Products”.
- Fieldsets:
  - Basics: category, title, slug, description, image_url (with read‑only thumbnail preview).
  - Pricing: price, currency.
  - Visibility: is_active.
  - Timestamps: created/updated (read‑only).
- List display shows thumbnail, category, price, currency, active status, and created timestamp.
- Inline edits: is_active is editable in the list.
- Performance: uses list_select_related(category) and pagination (50/page).
- Bulk actions:
  - Activate selected products
  - Deactivate selected products

Orders management

Order overview
- Orders have a status and a computed total.
- Inline “Items” allows editing OrderItem lines directly on the order page.
- After inline edits, totals recompute automatically.
- Deletion of paid orders is prevented by policy.
- CSV export available as an action: “Export selected Orders to CSV”.

Workflow transitions (short‑term flexible engine)
- Canonical map:
  - pending → paid → shipped → fulfilled
  - cancel from pending/paid → cancelled
  - refund from fulfilled → refunded
  - return from fulfilled → returned
- Actions:
  - “Apply workflow transition…” opens a form to choose a target state with an optional note and a Dry‑run option.
  - “Mark selected orders as Paid” and “Mark selected orders as Cancelled” route through the workflow engine if enabled.
- Dry‑run:
  - Validates guards without saving. Use it to check eligibility across a batch before applying.
- Audit log:
  - “Transitions” inline on the order detail shows the full timeline of state changes: when, from → to, who, and optional notes.

Feature flag (operations)
- WORKFLOW_ENABLED (default True)
  - When True: the admin uses the workflow engine for transitions and bulk actions.
  - When False: legacy direct status updates are used as a safe fallback.
- Configure via environment variable:
  - WORKFLOW_ENABLED=true|false

CSV export
- Orders list → select rows → Actions → “Export selected Orders to CSV”
- Export columns: id, email, status, total, created_at (ISO8601)

Troubleshooting
- Missing transitions:
  - If an order does not show a target state in the “Apply workflow transition…” form, it means there is no allowed transition from its current state per the canonical map.
- Permission issues:
  - Transitions require a logged‑in user. The built‑in guard role_allowed expects authenticated users with appropriate permissions (defaults to core.change_order). Superusers pass by default.
- Duplicate transition attempts:
  - Admin actions pass an idempotency key per order. Retrying an identical action will be treated as idempotent and will not duplicate logs or effects.
- Totals not updating after items change:
  - Totals recompute automatically on save via admin hooks. If the value appears stale, ensure the inline rows were saved and the page refreshed.
- “Paid” order cannot be deleted:
  - This is intentional. The admin prevents deleting paid orders to protect financial integrity.

Operational tips
- Use dry‑run on large batches to detect eligibility issues before applying transitions.
- You can toggle the entire workflow system off with the feature flag in case of emergencies.
- Keep docs/WORKFLOW.md handy for deeper technical details, guard/effect extension points, and rollout strategies.
