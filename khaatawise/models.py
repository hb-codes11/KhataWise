from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class BusinessProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="business")
    business_name = models.CharField(max_length=120, default="My business")
    gst_registered = models.BooleanField(default=False)
    income_tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10, validators=[MinValueValidator(0), MaxValueValidator(100)])
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=18, validators=[MinValueValidator(0), MaxValueValidator(100)])
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.business_name


class Transaction(models.Model):
    INCOME = "income"
    EXPENSE = "expense"
    TYPES = [(INCOME, "Income"), (EXPENSE, "Expense")]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="transactions")
    date = models.DateField()
    description = models.CharField(max_length=180)
    category = models.CharField(max_length=60, default="Other")
    transaction_type = models.CharField(max_length=8, choices=TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0.01)])
    gst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.description} — ₹{self.amount}"
