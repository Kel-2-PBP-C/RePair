from django.urls import path

from . import views
from .region_views import region_search

app_name = "accounts"

urlpatterns = [
    path("auth/", views.auth, name="auth"),
    path("google/", views.google_login, name="google_login"),
    path("google/callback/", views.google_callback, name="google_callback"),
    path("google/link/", views.google_link, name="google_link"),
    path("credentials/", views.credentials, name="credentials"),
    path("complete-profile/", views.complete_profile, name="complete_profile"),
    path("api/wilayah/", region_search, name="region_search"),
    path("login/", views.login, name="login"),
    path("register/", views.register, name="register"),
    path("profile/", views.profile, name="profile"),
    path("settings/", views.settings, name="settings"),
    path("logout/", views.logout, name="logout"),
]
