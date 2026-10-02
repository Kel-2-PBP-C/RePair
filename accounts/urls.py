from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("auth/", views.auth, name="auth"),
    path("login/", views.login, name="login"),
    path("register/", views.register, name="register"),
    path("profile/", views.profile, name="profile"),
    path("settings/", views.settings, name="settings"),
    path("logout/", views.logout, name="logout"),
]
