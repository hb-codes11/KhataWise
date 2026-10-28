from django.contrib.auth import views as auth_views
from django.urls import path
from . import views, web_healing

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("accounts/signup/", views.signup, name="signup"),
    path("accounts/login/", auth_views.LoginView.as_view(template_name="khaatawise/login.html"), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("transactions/add/", views.transaction_create, name="transaction_add"),
    path("transactions/<int:pk>/edit/", views.transaction_edit, name="transaction_edit"),
    path("transactions/<int:pk>/delete/", views.transaction_delete, name="transaction_delete"),
    path("reports/", views.report, name="report"),
    path("reports.csv", views.report_csv, name="report_csv"),
    path("settings/", views.business_settings, name="business_settings"),
    path("test-error/", views.trigger_error, name="trigger_error"),
    path("healer/", web_healing.healer_page, name="healer_info"),
    path("healer/status/", web_healing.cloud_status, name="cloud_healing_status"),
    path("healer/demo/", web_healing.recovery_demo, name="cloud_healing_demo"),
]
