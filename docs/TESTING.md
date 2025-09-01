# Manual Test Plan: SSR + HTMX + Alpine + SEO

This document provides a comprehensive, step-by-step checklist to validate the core architecture and interactive flows of the application.

Pre-requisites
- Server running at http://127.0.0.1:8000 (or your host)
- Tailwind/Vite assets loaded (dev: `npm run dev`; prod: `npm run build`)
- Some products present (admin or fixture). Images optional.

Conventions
- “Full render” = entire page via Django base.html.
- “Partial render” = HTMX fragment (underscore-prefixed template).
- Use browser DevTools → Network to verify HX requests and response bodies.
- Use DevTools Console to confirm no JS errors.

1) Navigation + SSR composition
1. Home redirect:
   - Visit “/”
   - Expected: HTTP 302 to “/products/”
2. Products full-render:
   - Visit “/products/”
   - Expected: status 200, full HTML (contains “<html” and base layout)
   - In page source, confirm:
     - Canonical link is present
     - OG/Twitter meta tags exist (title defaults to E‑Shop if not overridden)
3. Product detail full-render:
   - Click a product; URL like “/product/<slug>/”
   - Expected: status 200, full HTML, JSON-LD script tag present

2) HTMX: Product filtering + URL push
1. Search suggestions:
   - In the Search input, type “i”
   - Expected:
     - A dropdown appears (partial from templates/core/_search_suggestions.html)
     - On typing “ip”, see narrowed suggestions (max 8)
2. Filter form HX GET:
   - With some query (“ip”), wait ~300ms (debounced)
   - Expected:
     - Network shows GET “/products/?q=ip”
     - Response is a fragment (templates/core/_product_grid.html) not a full page
     - The “#product-grid” content is swapped without a full reload
     - Browser URL updates to include “?q=ip” (hx-push-url=true)
3. Category filter:
   - Choose a Category in the select; ensure results update via HX GET
   - URL reflects “&category=<slug>”

3) HTMX: Pagination
1. On “/products/?q=<something>” with multiple pages:
   - Click a page link (e.g., “2”)
   - Expected:
     - Network shows GET “/products/?page=2...”
     - Response is fragment (grid) and replaces only the grid container
     - URL updates with “page=2”
     - Prev/Next enabled/disabled states behave correctly

4) Wishlist toggle (session-based)
1. In a product card (grid):
   - Click heart button
   - Expected:
     - POST “/wishlist/toggle/”
     - Response swaps button outerHTML (filled vs outline heart)
     - Repeated clicks toggle the state consistently (session-based)
2. In product detail page:
   - The wishlist button appears next to Add-to-cart
   - Toggle and confirm appearance changes immediately via HTMX
3. Verify no comment text from the template appears next to heart

5) Add-to-cart + navbar badge updates
1. From product card:
   - Click “Add”
   - Expected:
     - POST “/cart/add”
     - Response is includes/_cart_badge.html and swaps navbar badge outerHTML
     - Badge increments
2. From product detail:
   - Set qty to 2 → Add to cart
   - Badge increments by 2
3. Confirm “cart-changed” events trigger badge reloads where expected

6) Cart page partial updates
1. Visit “/cart/”
   - Initial render is full page with “#cart-content” containing:
     - templates/core/_cart_table.html (line items)
     - templates/core/_cart_summary.html (order summary)
2. Update qty for one line:
   - Expected:
     - POST “/cart/update” with context=page
     - Response returns templates/core/_cart_content.html
     - The entire “#cart-content” is swapped (table + summary update)
     - Navbar badge is also updated (via HX-Trigger)
3. Remove line item:
   - POST “/cart/remove” with context=page
   - “#cart-content” updates; empty cart shows “Browse products” button

7) Alpine.js interactions
1. Navbar mobile menu:
   - On mobile width (or shrink window), click “Menu”
   - Expected: panel toggles (x-data open). No console errors.
2. Product detail image state:
   - Confirm container has x-data (currentImage). If product has an image, it shows; otherwise “No image”. (Extended gallery behavior can be added later.)

8) SEO checks
1. robots.txt:
   - Visit “/robots.txt”
   - Expected: text/plain content, includes “Sitemap: .../sitemap.xml”
2. sitemap.xml:
   - Visit “/sitemap.xml”
   - Expected: XML with URLs for “/”, “/products/”, and product detail pages
3. Canonical:
   - On /products/ and product detail, page head includes a canonical link with current absolute URL
4. Product detail SEO:
   - Meta description present (truncated product.description)
   - Script type “application/ld+json” present; includes name, description, price, priceCurrency, availability
5. OG/Twitter defaults:
   - og:title and twitter:title default to “E‑Shop” unless overridden

9) Resilience + UX hints
1. Loading indicators:
   - On filter/ pagination requests, “Loading...” indicator is visible within grid (htmx-indicator) and disappears after swap
2. Network failures (optional):
   - Throttle network and ensure the UI remains usable; no script crashes
3. Cache/cold load:
   - Hard refresh; ensure Vite assets load and no duplicate console errors

Known quick checks via Network/Response
- Grid update response must NOT include “<html” tag (fragment mode).
- Cart badge response is a small “<span id="cart-badge">...”.
- Cart content update returns a container with table + summary.

Appendix: Quick endpoints checklist
- GET / → 302 → /products/
- GET /products/ → 200 full
- GET /products/?q=... → 200 fragment (via HTMX)
- GET /search/suggest/?q=... → 200 fragment (list)
- POST /wishlist/toggle/ (HTMX) → 200 fragment (button)
- POST /cart/add (HTMX) → 200 fragment (badge)
- POST /cart/update (HTMX, context=page) → 200 fragment (cart content)
- POST /cart/remove (HTMX, context=page) → 200 fragment (cart content)
- GET /robots.txt → 200 text/plain
- GET /sitemap.xml → 200 XML

## Pre-commit: run Django tests automatically before each commit

This project includes a pre-commit hook that runs the Django test suite on every commit and prints the report in your terminal. If tests fail, the commit is blocked.

Setup (one-time)
1) Install dev dependency (choose one)
- With uv:
  - uv pip install -r requirements-dev.txt
- With pip:
  - pip install -r requirements-dev.txt

2) Install git hooks
- pre-commit install

3) Verify pre-commit is active
- pre-commit run --all-files
  - This will run the configured hooks. You should see the “Run Django test suite before commit” hook pass.

What the hook does
- Configuration: [.pre-commit-config.yaml](../.pre-commit-config.yaml)
- Hook runs:
  - uv run python manage.py test -v 2 (if uv is installed)
  - otherwise: python manage.py test -v 2
- Output: The Django test runner prints its result directly in your terminal before the commit completes.

Typical commands
- First time:
  - uv pip install -r requirements-dev.txt  (or pip install -r requirements-dev.txt)
  - pre-commit install
- Manually re-run hook on all files:
  - pre-commit run --all-files
- Temporarily bypass tests for an emergency commit (not recommended):
  - git commit -m "msg" --no-verify

Notes
- Ensure your test database can be created (SQLite by default) and that required migrations are present.
- The test suite uses fixtures where needed (see [core/tests.py](../core/tests.py) and [core/fixtures/sample.json](../core/fixtures/sample.json)).
- If you use a virtual environment, activate it prior to running pre-commit so the python and dependencies resolve correctly.


# Admin QA — Orders Workflow and Catalog

This section adds step‑by‑step checks for the Django Admin, covering the flexible Order workflow engine, audit logging, CSV export, and catalog management. See the workflow overview in [docs/WORKFLOW.md](docs/WORKFLOW.md). Admin integrations live in [core/admin.py](core/admin.py) and the action template [templates/admin/core/order/apply_transition.html](templates/admin/core/order/apply_transition.html). The feature flag is defined in [ecom/settings.py](ecom/settings.py).

Pre‑requisites
- A server is running and accessible at your admin URL (default /admin/).
- A superuser exists and can log in.
- Some products exist (either via fixtures or created through admin).
- Feature flag:
  - WORKFLOW_ENABLED defaults to True. To test legacy fallback, set env var WORKFLOW_ENABLED=false and restart the server.

A) Catalog admin sanity
1) Categories
   - Visit /admin/core/category/.
   - Create at least one category. Confirm slug is pre‑populated.
   - List view shows “Products” count and is searchable by title or slug.

2) Products
   - Visit /admin/core/product/.
   - Create a product:
     - Fill Basics (category, title, slug, description, image_url).
     - Fill Pricing (price, currency).
     - Visibility (is_active True).
   - Save and confirm:
     - List view shows the image thumbnail in the “Image” column.
     - “is_active” is inline editable from list view.
     - Pagination is 50 per page.
     - Filters on category and is_active work.
   - Bulk actions:
     - Select a few products → Actions → “Activate selected products” → confirm message.
     - Then “Deactivate selected products” → confirm message.

B) Orders admin — totals recompute and deletion guard
1) Create an Order:
   - Visit /admin/core/order/ → Add Order.
   - Fill contact/shipping fields and save (status defaults to pending).
   - Add OrderItems inline (product, quantity, unit_price, currency).
   - Save and confirm Total is computed and matches sum of subtotals.

2) Totals recompute after inline edits:
   - Change one inline quantity or unit_price and save.
   - Confirm Total updated accordingly.

3) Deletion guard:
   - For an order with status “paid”, attempt to delete.
   - Expected: deletion is blocked (policy safety).

C) Orders admin — CSV export
1) From the Orders list, select 1–3 orders → Actions → “Export selected Orders to CSV”.
2) Confirm a CSV downloads and contains header: id,email,status,total,created_at; and rows for selected orders.

D) Orders admin — workflow transitions (Option B engine)
Canonical map:
- pending → paid → shipped → fulfilled
- cancel from pending/paid → cancelled
- refund from fulfilled → refunded
- return from fulfilled → returned

1) Dry‑run validation
   - From the Orders list:
     - Select one pending order → Actions → “Apply workflow transition…”.
     - Pick target “paid”, add note “dry”, check “Dry run”.
     - Submit and expect a success validation message; order status remains pending; no OrderTransitionLog row created.

2) Real transition pending → paid
   - Repeat without Dry run.
   - Expected:
     - Order status becomes “paid”.
     - One OrderTransitionLog entry exists showing from_state=pending, to_state=paid in the “Transitions” inline on detail.

3) paid → shipped
   - Use “Apply workflow transition…” with target “shipped”.
   - Expected: status shipped; another OrderTransitionLog entry appears.

4) shipped → fulfilled
   - Transition to “fulfilled”.
   - Expected: status fulfilled; another log entry appears.

5) cancel allowed paths
   - Create a fresh pending order; transition to “cancelled”.
     - Expected: success; log entry pending → cancelled.
   - Create a fresh order, move to “paid”, then transition to “cancelled”.
     - Expected: success; log entry paid → cancelled.

6) refund/return from fulfilled
   - For a fulfilled order:
     - Transition to “refunded”:
       - Expected: success; log entry fulfilled → refunded.
     - Alternatively, transition to “returned”:
       - Expected: success; log entry fulfilled → returned.
   - Note: these are stubs for effects (no integration), but audit should still log.

7) Bulk transitions
   - Prepare two orders:
     - One pending (eligible for “cancelled”).
     - One fulfilled (not eligible for “cancelled”).
   - Select both → “Apply workflow transition…”:
     - Dry run to target “cancelled”:
       - Expected: validation success only for pending; no DB changes; no logs created.
     - Real apply to target “cancelled”:
       - Expected: pending becomes cancelled; fulfilled remains fulfilled; one log entry for the pending order only.

8) Idempotency behavior
   - Apply the same real transition twice to the same target (e.g., pending → paid) via the admin action.
   - Expected: only a single OrderTransitionLog exists for that (order, to_state) idempotency key (the UI message may still show success for the second attempt; rely on the log count to confirm no duplicate entry).

9) Feature flag fallback
   - Set WORKFLOW_ENABLED=false via environment; restart the server.
   - Repeat “Mark selected orders as Paid” and “Mark selected orders as Cancelled”.
   - Expected: direct status updates occur (legacy path), no OrderTransitionLog rows are created by these actions.

Troubleshooting
- No “Apply workflow transition…” option:
  - Ensure you’re on the Orders list page and have selected at least one order.
- No target options in action form:
  - The current state has no defined transitions in the canonical map (see [docs/WORKFLOW.md](docs/WORKFLOW.md)).
- Missing audit rows:
  - Confirm the transition was not a Dry run and WORKFLOW_ENABLED=True.
- Static files warnings during tests:
  - Tests temporarily use the non‑manifest staticfiles storage for admin CSS/JS (see [ecom/settings.py](ecom/settings.py)).
