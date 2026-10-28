from datetime import date
from decimal import Decimal
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from .models import BusinessProfile, Transaction


class KhaataWiseTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner", password="a-secure-test-password")
        self.profile = BusinessProfile.objects.create(user=self.user, business_name="Corner Shop", gst_registered=True)
        self.client.force_login(self.user)

    def add_transaction(self, kind, amount, gst="0", day=date(2026, 5, 2), description="Test entry"):
        return Transaction.objects.create(user=self.user, date=day, description=description, category="Sales",
                                          transaction_type=kind, amount=Decimal(amount), gst_amount=Decimal(gst))

    def test_dashboard_summarizes_financial_year_and_estimates(self):
        self.add_transaction(Transaction.INCOME, "100000", "18000")
        self.add_transaction(Transaction.EXPENSE, "40000", "3600")
        response = self.client.get(reverse("dashboard"), {"fy": "2026"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["income"], Decimal("100000"))
        self.assertEqual(response.context["expenses"], Decimal("40000"))
        self.assertEqual(response.context["profit"], Decimal("60000"))
        self.assertEqual(response.context["tax_estimate"], Decimal("6000"))
        self.assertEqual(response.context["gst_due"], Decimal("14400"))

    def test_transaction_create_uses_signed_in_user(self):
        response = self.client.post(reverse("transaction_add"), {
            "date": "2026-05-02", "description": "New sale", "category": "Sales",
            "transaction_type": "income", "amount": "1200.00", "gst_amount": "216.00",
        })
        self.assertRedirects(response, reverse("dashboard"))
        self.assertTrue(Transaction.objects.filter(user=self.user, description="New sale").exists())

    def test_expense_create_and_dashboard_remain_available(self):
        response = self.client.post(reverse("transaction_add"), {
            "date": "2026-05-02", "description": "Office rent", "category": "Rent",
            "transaction_type": "expense", "amount": "1200.00", "gst_amount": "0.00",
        })
        self.assertRedirects(response, reverse("dashboard"))
        transaction = Transaction.objects.get(user=self.user, description="Office rent")
        self.assertEqual(transaction.transaction_type, Transaction.EXPENSE)
        self.assertEqual(transaction.amount, Decimal("1200.00"))
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)

    def test_new_transaction_form_defaults_to_income(self):
        response = self.client.get(reverse("transaction_add"))
        self.assertEqual(response.context["form"]["transaction_type"].value(), Transaction.INCOME)

    def test_user_cannot_edit_another_users_transaction(self):
        other = User.objects.create_user(username="other", password="a-secure-test-password")
        transaction = Transaction.objects.create(user=other, date=date(2026, 5, 2), description="Private",
            category="Other", transaction_type=Transaction.INCOME, amount=Decimal("100"))
        self.assertEqual(self.client.get(reverse("transaction_edit", args=[transaction.pk])).status_code, 404)

    def test_csv_report_contains_summary(self):
        self.add_transaction(Transaction.INCOME, "2500")
        response = self.client.get(reverse("report_csv"), {"fy": "2026"})
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn(b"Profit / (loss)", response.content)

    def test_income_tax_estimate_is_zero_for_a_loss(self):
        self.add_transaction(Transaction.INCOME, "100")
        self.add_transaction(Transaction.EXPENSE, "200")
        response = self.client.get(reverse("report"), {"fy": "2026"})
        self.assertEqual(response.context["tax_estimate"], Decimal("0"))


class AuthenticationTests(TestCase):
    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('dashboard')}")

    def test_signup_creates_business_profile(self):
        response = self.client.post(reverse("signup"), {
            "username": "new-owner", "email": "owner@example.com",
            "password1": "unusual-test-password-8241", "password2": "unusual-test-password-8241",
        })
        self.assertRedirects(response, reverse("dashboard"))
        self.assertTrue(BusinessProfile.objects.filter(user__username="new-owner").exists())


class WebHealingTests(TestCase):
    def test_healing_page_is_available_without_local_server(self):
        response = self.client.get('/healer/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Run recovery demo')
        self.assertNotContains(response, 'localhost')

    def test_web_demo_detects_two_faults_and_verifies_retry(self):
        response = self.client.post('/healer/demo/')
        data = response.json()
        self.assertEqual(data['status'], 'resolved')
        self.assertEqual(data['iterations'], 3)
        self.assertEqual(data['verification']['amount'], '1250.00')
        self.assertFalse(data['verification']['production_data_changed'])
        self.assertEqual(Transaction.objects.count(), 0)

    def test_demo_requires_post_and_csrf(self):
        from django.test import Client
        self.assertEqual(self.client.get('/healer/demo/').status_code, 405)
        self.assertEqual(Client(enforce_csrf_checks=True).post('/healer/demo/').status_code, 403)
