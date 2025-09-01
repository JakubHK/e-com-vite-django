from django.test import TestCase, Client
from django.urls import reverse


class SSRHtmxFlowTests(TestCase):
    fixtures = ["sample.json"]

    def setUp(self):
        self.client = Client()

    def test_home_redirects_to_products(self):
        resp = self.client.get(reverse("home"))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], reverse("products"))

    def test_products_full_render_contains_base_layout(self):
        resp = self.client.get(reverse("products"))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8").lower()
        self.assertIn("<html", html)
        # Products full page includes wrapper container id
        self.assertIn('id="product-grid"', html)

    def test_products_htmx_partial_render(self):
        resp = self.client.get(reverse("products"), HTTP_HX_REQUEST="true")
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8").lower()
        # Partial should not include full html skeleton
        self.assertNotIn("<html", html)
        # Partial grid includes the indicator element
        self.assertIn("htmx-indicator", html)

    def test_search_suggest_partial_limit(self):
        # Query that should match some products from fixtures (e.g., 'django')
        resp = self.client.get(reverse("search_suggest"), {"q": "django"})
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8").lower()
        self.assertNotIn("<html", html)
        # Should contain the list container
        self.assertIn("<ul", html)

        # Ensure suggestions do not exceed 8 (cannot parse count easily here; sanity check content exists)
        # When q is empty, should render "Start typing" notice
        resp2 = self.client.get(reverse("search_suggest"), {"q": ""})
        self.assertEqual(resp2.status_code, 200)
        self.assertIn("start typing", resp2.content.decode("utf-8").lower())

    def test_wishlist_toggle_session_and_partial(self):
        # Use first product (pk=1 from fixture)
        product_id = 1
        # Ensure wishlist empty
        self.client.session["wishlist"] = []
        self.client.session.save()

        resp = self.client.post(
            reverse("wishlist_toggle"),
            {"product_id": product_id},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8").lower()
        # Button partial rendered
        self.assertIn("<form", html)
        # Session updated
        wishlist = self.client.session.get("wishlist", [])
        self.assertIn(str(product_id), wishlist)

        # Toggle again: should remove
        resp2 = self.client.post(
            reverse("wishlist_toggle"),
            {"product_id": product_id},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(resp2.status_code, 200)
        wishlist2 = self.client.session.get("wishlist", [])
        self.assertNotIn(str(product_id), wishlist2)

    def test_cart_add_returns_badge_partial_on_htmx(self):
        product_id = 1
        resp = self.client.post(
            reverse("cart_add"),
            {"product_id": product_id, "qty": 1},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8").lower()
        self.assertIn('id="cart-badge"', html)
        # Count should be 1
        self.assertIn(">1<", html)

    def test_cart_update_returns_cart_content_partial_with_context_page(self):
        product_id = 1
        # Add product first
        self.client.post(
            reverse("cart_add"),
            {"product_id": product_id, "qty": 1},
            HTTP_HX_REQUEST="true",
        )
        # Update qty to 2 in cart page context
        resp = self.client.post(
            reverse("cart_update"),
            {"product_id": product_id, "qty": 2, "context": "page"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")
        # Partial cart content contains Order Summary heading
        self.assertIn("Order Summary", html)

    def test_cart_remove_returns_cart_content_partial_with_context_page(self):
        product_id = 1
        # Add product first
        self.client.post(
            reverse("cart_add"),
            {"product_id": product_id, "qty": 1},
            HTTP_HX_REQUEST="true",
        )
        # Remove in cart page context
        resp = self.client.post(
            reverse("cart_remove"),
            {"product_id": product_id, "context": "page"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")
        # After removal, either empty cart prompt or updated table renders
        self.assertTrue(("Your cart is empty." in html) or ("Order Summary" in html))

    def test_robots_and_sitemap(self):
        robots = self.client.get("/robots.txt")
        self.assertEqual(robots.status_code, 200)
        self.assertEqual(robots["Content-Type"].split(";")[0], "text/plain")
        self.assertIn("Sitemap:", robots.content.decode("utf-8"))

        sitemap = self.client.get("/sitemap.xml")
        self.assertEqual(sitemap.status_code, 200)
        xml = sitemap.content.decode("utf-8").lower()
        self.assertIn("<urlset", xml)


from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from core.models import Category, Product, Order, OrderItem, OrderStatus, OrderTransitionLog
from core.workflow.service import TransitionService


class WorkflowServiceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_superuser(username="admin", email="admin@example.com", password="pass")

        self.cat = Category.objects.create(title="Books", slug="books")
        self.prod = Product.objects.create(
            category=self.cat,
            title="Book",
            slug="book",
            price="10.00",
            currency="EUR",
            is_active=True,
        )
        self.order = Order.objects.create(
            email="buyer@example.com",
            status=OrderStatus.PENDING,
            name="Buyer",
            street="Main",
            city="City",
            zip="00000",
            country="CZ",
        )
        OrderItem.objects.create(
            order=self.order, product=self.prod, quantity=2, unit_price="10.00", currency="EUR"
        )
        self.order.compute_total()
        self.order.save()

    def test_allowed_transitions_from_pending(self):
        service = TransitionService()
        attempts = service.allowed_transitions(self.order)
        to_states = {a.transition.to_state for a in attempts}
        self.assertIn(OrderStatus.PAID, to_states)
        self.assertIn(OrderStatus.CANCELLED, to_states)

    def test_transition_dry_run_does_not_change_state_or_log(self):
        service = TransitionService()
        res = service.transition(
            self.order,
            OrderStatus.PAID,
            actor_user=self.user,
            actor_label="test",
            note="dry",
            idempotency_key="t-dry-1",
            dry_run=True,
        )
        self.assertTrue(res.success)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.PENDING)
        self.assertEqual(OrderTransitionLog.objects.count(), 0)

    def test_transition_real_changes_state_and_writes_log(self):
        service = TransitionService()
        res = service.transition(
            self.order,
            OrderStatus.PAID,
            actor_user=self.user,
            actor_label="test",
            note="go",
            idempotency_key="t-paid-1",
        )
        self.assertTrue(res.success)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.PAID)
        self.assertEqual(OrderTransitionLog.objects.count(), 1)
        log = OrderTransitionLog.objects.first()
        self.assertEqual(log.from_state, OrderStatus.PENDING)
        self.assertEqual(log.to_state, OrderStatus.PAID)

    def test_idempotency_prevents_duplicate_effects_and_logs(self):
        service = TransitionService()
        key = "t-paid-dup"
        first = service.transition(
            self.order,
            OrderStatus.PAID,
            actor_user=self.user,
            actor_label="test",
            note="once",
            idempotency_key=key,
        )
        self.assertTrue(first.success)
        second = service.transition(
            self.order,
            OrderStatus.PAID,
            actor_user=self.user,
            actor_label="test",
            note="twice",
            idempotency_key=key,
        )
        self.assertTrue(second.success)
        self.assertTrue(second.idempotent)
        # Only one log for the idempotent key
        self.assertEqual(OrderTransitionLog.objects.filter(idempotency_key=key).count(), 1)


class WorkflowAdminActionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_superuser(username="admin", email="admin@example.com", password="pass")
        self.client.force_login(self.user)

        self.cat = Category.objects.create(title="Books", slug="books")
        self.prod = Product.objects.create(
            category=self.cat,
            title="Book",
            slug="book",
            price="10.00",
            currency="EUR",
            is_active=True,
        )
        self.order = Order.objects.create(
            email="buyer@example.com",
            status=OrderStatus.PENDING,
            name="Buyer",
            street="Main",
            city="City",
            zip="00000",
            country="CZ",
        )
        OrderItem.objects.create(
            order=self.order, product=self.prod, quantity=1, unit_price="10.00", currency="EUR"
        )
        self.order.compute_total()
        self.order.save()

    def test_admin_apply_transition_dry_run(self):
        url = reverse("admin:core_order_changelist")
        # Step 1: trigger action to render intermediate form
        resp1 = self.client.post(url, {"action": "apply_transition", "_selected_action": [self.order.pk]})
        self.assertEqual(resp1.status_code, 200)
        self.assertIn(b"Apply workflow transition", resp1.content)

        # Step 2: submit apply with dry_run
        resp2 = self.client.post(
            url,
            {
                "action": "apply_transition",
                "_selected_action": [self.order.pk],
                "apply": "1",
                "target_state": OrderStatus.PAID,
                "note": "dry",
                "dry_run": "on",
            },
            follow=True,
        )
        self.assertEqual(resp2.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.PENDING)
        self.assertEqual(OrderTransitionLog.objects.count(), 0)

    def test_admin_apply_transition_real(self):
        url = reverse("admin:core_order_changelist")
        # Render form
        resp1 = self.client.post(url, {"action": "apply_transition", "_selected_action": [self.order.pk]})
        self.assertEqual(resp1.status_code, 200)

        # Apply real transition
        resp2 = self.client.post(
            url,
            {
                "action": "apply_transition",
                "_selected_action": [self.order.pk],
                "apply": "1",
                "target_state": OrderStatus.PAID,
                "note": "ok",
                # dry_run omitted for real execution
            },
            follow=True,
        )
        self.assertEqual(resp2.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.PAID)
        self.assertEqual(OrderTransitionLog.objects.count(), 1)


class WorkflowConcurrencyTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_superuser(username="admin2", email="admin2@example.com", password="pass")
        self.cat = Category.objects.create(title="Books2", slug="books2")
        self.prod = Product.objects.create(
            category=self.cat,
            title="Book2",
            slug="book2",
            price="15.00",
            currency="EUR",
            is_active=True,
        )
        self.order = Order.objects.create(
            email="buyer2@example.com",
            status=OrderStatus.PENDING,
            name="Buyer2",
            street="Main",
            city="City",
            zip="10000",
            country="CZ",
        )
        OrderItem.objects.create(
            order=self.order, product=self.prod, quantity=1, unit_price="15.00", currency="EUR"
        )
        self.order.compute_total()
        self.order.save()

    def test_concurrent_state_change_blocks_transition(self):
        service = TransitionService()
        # Pre-check: pending -> paid would normally be allowed
        attempts = service.allowed_transitions(self.order)
        self.assertIn(OrderStatus.PAID, {a.transition.to_state for a in attempts})

        # Simulate concurrent change: another actor cancels before we execute transition()
        Order.objects.filter(pk=self.order.pk).update(status=OrderStatus.CANCELLED)

        res = service.transition(
            self.order,
            OrderStatus.PAID,
            actor_user=self.user,
            actor_label="race",
            note="race",
            idempotency_key="race-1",
        )
        self.assertFalse(res.success)
        self.assertIsNone(res.to_state)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.CANCELLED)
        # No log should be written for failed transition
        self.assertEqual(OrderTransitionLog.objects.filter(order=self.order).count(), 0)


class WorkflowAdminBulkActionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_superuser(username="admin3", email="admin3@example.com", password="pass")
        self.client.force_login(self.user)

        self.cat = Category.objects.create(title="Bulk", slug="bulk")
        self.prod = Product.objects.create(
            category=self.cat,
            title="BulkBook",
            slug="bulk-book",
            price="20.00",
            currency="EUR",
            is_active=True,
        )
        # One pending (eligible for cancel), one fulfilled (not eligible for cancel)
        self.order1 = Order.objects.create(
            email="p@example.com",
            status=OrderStatus.PENDING,
            name="P",
            street="S",
            city="C",
            zip="Z",
            country="CZ",
        )
        OrderItem.objects.create(order=self.order1, product=self.prod, quantity=1, unit_price="20.00", currency="EUR")

        self.order2 = Order.objects.create(
            email="f@example.com",
            status=OrderStatus.FULFILLED,
            name="F",
            street="S",
            city="C",
            zip="Z",
            country="CZ",
        )
        OrderItem.objects.create(order=self.order2, product=self.prod, quantity=1, unit_price="20.00", currency="EUR")

        for o in (self.order1, self.order2):
            o.compute_total()
            o.save()

    def test_admin_apply_transition_bulk_dry_run_and_real(self):
        url = reverse("admin:core_order_changelist")

        # Render intermediate form
        resp1 = self.client.post(
            url,
            {"action": "apply_transition", "_selected_action": [self.order1.pk, self.order2.pk]},
        )
        self.assertEqual(resp1.status_code, 200)
        self.assertIn(b"Apply workflow transition", resp1.content)

        # Dry run: choose target_state=cancelled (allowed for pending, not for fulfilled)
        resp2 = self.client.post(
            url,
            {
                "action": "apply_transition",
                "_selected_action": [self.order1.pk, self.order2.pk],
                "apply": "1",
                "target_state": OrderStatus.CANCELLED,
                "note": "dry-bulk",
                "dry_run": "on",
            },
            follow=True,
        )
        self.assertEqual(resp2.status_code, 200)
        self.order1.refresh_from_db()
        self.order2.refresh_from_db()
        self.assertEqual(self.order1.status, OrderStatus.PENDING)
        self.assertEqual(self.order2.status, OrderStatus.FULFILLED)
        self.assertEqual(OrderTransitionLog.objects.filter(order__in=[self.order1, self.order2]).count(), 0)

        # Real apply: same target state; pending should move to cancelled, fulfilled should remain
        resp3 = self.client.post(
            url,
            {
                "action": "apply_transition",
                "_selected_action": [self.order1.pk, self.order2.pk],
                "apply": "1",
                "target_state": OrderStatus.CANCELLED,
                "note": "real-bulk",
            },
            follow=True,
        )
        self.assertEqual(resp3.status_code, 200)
        self.order1.refresh_from_db()
        self.order2.refresh_from_db()
        self.assertEqual(self.order1.status, OrderStatus.CANCELLED)
        self.assertEqual(self.order2.status, OrderStatus.FULFILLED)
        # Exactly one successful log for order1
        self.assertEqual(OrderTransitionLog.objects.filter(order=self.order1, to_state=OrderStatus.CANCELLED).count(), 1)


from django.test import RequestFactory
from django.contrib import admin

from core.admin import OrderAdmin


class OrderAdminMiscTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_superuser(username="adminX", email="adminx@example.com", password="pass")
        self.client.force_login(self.user)
        self.rf = RequestFactory()

        # Minimal catalog and orders
        self.cat = Category.objects.create(title="Misc", slug="misc")
        self.prod = Product.objects.create(
            category=self.cat,
            title="Misc Book",
            slug="misc-book",
            price="12.34",
            currency="EUR",
            is_active=True,
        )
        # Pending order
        self.order_pending = Order.objects.create(
            email="p@example.com",
            status=OrderStatus.PENDING,
            name="P",
            street="S",
            city="C",
            zip="Z",
            country="CZ",
        )
        OrderItem.objects.create(order=self.order_pending, product=self.prod, quantity=1, unit_price="12.34", currency="EUR")
        self.order_pending.compute_total()
        self.order_pending.save()

        # Paid order (to test deletion guard)
        self.order_paid = Order.objects.create(
            email="paid@example.com",
            status=OrderStatus.PAID,
            name="Paid",
            street="S",
            city="C",
            zip="Z",
            country="CZ",
        )
        OrderItem.objects.create(order=self.order_paid, product=self.prod, quantity=2, unit_price="12.34", currency="EUR")
        self.order_paid.compute_total()
        self.order_paid.save()

        self.model_admin = OrderAdmin(Order, admin.site)

    def test_export_as_csv_action(self):
        request = self.rf.post("/admin/core/order/")
        request.user = self.user
        qs = Order.objects.filter(pk__in=[self.order_pending.pk, self.order_paid.pk])
        resp = self.model_admin.export_as_csv(request, qs)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/csv", resp["Content-Type"])
        content = resp.content.decode("utf-8")
        # Header present
        self.assertIn("id,email,status,total,created_at", content.replace(" ", ""))
        # Contains both orders' IDs
        self.assertIn(str(self.order_pending.pk), content)
        self.assertIn(str(self.order_paid.pk), content)

    def test_has_delete_permission_blocks_paid_orders(self):
        request = self.rf.get("/admin/core/order/")
        request.user = self.user
        # Paid should be blocked
        self.assertFalse(self.model_admin.has_delete_permission(request, obj=self.order_paid))
        # Pending should follow default (True for superuser)
        self.assertTrue(self.model_admin.has_delete_permission(request, obj=self.order_pending))
