from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("landing/", views.landing, name="landing"),
    path("terms/", views.policies, name="terms"),
    path("privacy/", views.policies, name="privacy"),
]
