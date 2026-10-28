import csv
import json
from calendar import month_abbr
from datetime import date
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
import logging
from .forms import BusinessProfileForm, SignUpForm, TransactionForm

logger = logging.getLogger("khaatawise")
from .models import BusinessProfile, Transaction


def current_fy_year():
    today = timezone.localdate()
    return today.year if today.month >= 4 else today.year - 1


def fy_bounds(year):
    return date(year, 4, 1), date(year + 1, 3, 31)


def selected_year(request):
    try:
        year = int(request.GET.get("fy", current_fy_year()))
        if 2000 <= year <= current_fy_year() + 1:
            return year
    except (TypeError, ValueError):
        pass
    return current_fy_year()


def financial_year_options(selected):
    years = list(range(current_fy_year(), current_fy_year() - 6, -1))
    if selected not in years:
        years.insert(0, selected)
    return [(year, f"FY {year}–{str(year + 1)[-2:]}") for year in years]


def profile_for(user):
    profile, _ = BusinessProfile.objects.get_or_create(user=user)
    return profile


def financial_summary(user, year):
    start, end = fy_bounds(year)
    transactions = Transaction.objects.filter(user=user, date__range=(start, end))
    income = transactions.filter(transaction_type=Transaction.INCOME).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    expenses = transactions.filter(transaction_type=Transaction.EXPENSE).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    gross_income = transactions.filter(transaction_type=Transaction.INCOME).aggregate(total=Sum("gst_amount"))["total"] or Decimal("0")
    input_gst = transactions.filter(transaction_type=Transaction.EXPENSE).aggregate(total=Sum("gst_amount"))["total"] or Decimal("0")
    profit = income - expenses
    profile = profile_for(user)
    tax_estimate = max(profit, Decimal("0")) * profile.income_tax_rate / Decimal("100")
    gst_due = max(gross_income - input_gst, Decimal("0")) if profile.gst_registered else Decimal("0")
    months = []
    for month in range(4, 13):
        months.append((month, month_abbr[month]))
    for month in range(1, 4):
        months.append((month, month_abbr[month]))
    monthly = []
    for month, label in months:
        sums = transactions.filter(date__month=month).values("transaction_type").annotate(total=Sum("amount"))
        values = {row["transaction_type"]: row["total"] or Decimal("0") for row in sums}
        monthly.append({"label": label, "income": values.get(Transaction.INCOME, Decimal("0")), "expenses": values.get(Transaction.EXPENSE, Decimal("0"))})
    return {"start": start, "end": end, "transactions": transactions, "income": income,
            "expenses": expenses, "profit": profit, "tax_estimate": tax_estimate,
            "gst_due": gst_due, "monthly": monthly,
            "income_gst": gross_income, "input_gst": input_gst}


def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        BusinessProfile.objects.create(user=user, business_name=f"{user.username}'s business")
        login(request, user)
        messages.success(request, "Your workspace is ready. Add your first transaction to get started.")
        return redirect("dashboard")
    return render(request, "khaatawise/signup.html", {"form": form})


@login_required
def dashboard(request):
    year = selected_year(request)
    data = financial_summary(request.user, year)
    data.update({"fy": year, "fy_end": str(year + 1)[-2:], "financial_years": financial_year_options(year), "profile": profile_for(request.user),
                 "recent": data["transactions"][:6], "chart_json": json.dumps([
                     {"label": m["label"], "income": float(m["income"]), "expenses": float(m["expenses"])} for m in data["monthly"]
                 ])})
    return render(request, "khaatawise/dashboard.html", data)


@login_required
def transaction_create(request):
    form = TransactionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        transaction = form.save(commit=False)
        transaction.user = request.user
        # BUG: Faulty expense handling - CRASHES the server when creating expenses
        if transaction.transaction_type == Transaction.EXPENSE:
            logger.critical("FAULTY FEATURE CRASH: Expense creation triggers server crash for user %s", request.user.username)
            raise RuntimeError("CRITICAL FAULT: Expense module has a fatal bug - server crash triggered intentionally for logging demo")
        transaction.save()
        messages.success(request, "Transaction saved.")
        return redirect("dashboard")
    return render(request, "khaatawise/transaction_form.html", {"form": form, "title": "Add transaction"})


@login_required
def transaction_edit(request, pk):
    transaction = get_object_or_404(Transaction, pk=pk, user=request.user)
    form = TransactionForm(request.POST or None, instance=transaction)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Transaction updated.")
        return redirect("dashboard")
    return render(request, "khaatawise/transaction_form.html", {"form": form, "title": "Edit transaction"})


@login_required
def transaction_delete(request, pk):
    transaction = get_object_or_404(Transaction, pk=pk, user=request.user)
    if request.method == "POST":
        transaction.delete()
        messages.success(request, "Transaction deleted.")
        return redirect("dashboard")
    return render(request, "khaatawise/transaction_confirm_delete.html", {"transaction": transaction})


@login_required
def report(request):
    year = selected_year(request)
    data = financial_summary(request.user, year)
    data.update({"fy": year, "fy_end": str(year + 1)[-2:], "profile": profile_for(request.user)})
    return render(request, "khaatawise/report.html", data)


@login_required
def report_csv(request):
    year = selected_year(request)
    data = financial_summary(request.user, year)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="khaatawise-FY{year}-{year + 1}-report.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(["KhaataWise profit and tax estimate", f"FY {year}-{str(year + 1)[-2:]}"])
    writer.writerow(["Period", data["start"], data["end"]])
    writer.writerow([])
    writer.writerow(["Date", "Type", "Description", "Category", "Amount (INR)", "GST (INR)"])
    def safe_cell(value):
        value = str(value)
        return f"'{value}" if value.startswith(("=", "+", "-", "@", "\t", "\r")) else value
    for transaction in data["transactions"]:
        writer.writerow([transaction.date, transaction.get_transaction_type_display(), safe_cell(transaction.description),
                         safe_cell(transaction.category), transaction.amount, transaction.gst_amount])
    writer.writerow([])
    writer.writerow(["Income", data["income"]])
    writer.writerow(["Expenses", data["expenses"]])
    writer.writerow(["Profit / (loss)", data["profit"]])
    writer.writerow(["Estimated income tax", data["tax_estimate"]])
    writer.writerow(["Estimated net GST", data["gst_due"]])
    writer.writerow(["Disclaimer", "Planning estimate only. Verify applicable rules and figures with a qualified tax professional."])
    return response


@login_required
def business_settings(request):
    profile = profile_for(request.user)
    form = BusinessProfileForm(request.POST or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Business settings saved.")
        return redirect("business_settings")
    return render(request, "khaatawise/settings.html", {"form": form, "profile": profile})


@login_required
def trigger_error(request):
    """View to trigger a test error for verifying error logging."""
    logger.error("Test error triggered by user %s", request.user.username)
    raise RuntimeError("This is a test error for verifying error logging. It is intentional and safe.")


def healer_info(request):
    """Public info endpoint about the MVP AI Self-Healing Server."""
    from django.http import JsonResponse
    return JsonResponse({
        "project": "Autonomous AI Self-Healing Server (MVP)",
        "test_target": "KhaataWise",
        "poll_frequency": "Every 5 seconds",
        "watched_logs": ["logs/error.log", "logs/input.log", "logs/output.log", "logs/server.log"],
        "self_healing_mechanism": "system.txt prompt -> AI JSON packet -> execute terminal cmd -> resend mry + system.txt -> quit exit guard",
        "local_dashboard": "http://localhost:8080"
    })
