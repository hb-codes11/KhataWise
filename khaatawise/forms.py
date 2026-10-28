from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import BusinessProfile, Transaction


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)
    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")


class TransactionForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound and not self.instance.pk:
            self.fields["transaction_type"].initial = Transaction.INCOME

    class Meta:
        model = Transaction
        fields = ("date", "description", "category", "transaction_type", "amount", "gst_amount")
        widgets = {"date": forms.DateInput(attrs={"type": "date"})}
        labels = {"transaction_type": "Income or expense"}


class BusinessProfileForm(forms.ModelForm):
    class Meta:
        model = BusinessProfile
        fields = ("business_name", "gst_registered", "income_tax_rate", "gst_rate")
