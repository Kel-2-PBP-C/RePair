from django.urls import path

from main_page.views import show_main

from . import views

app_name = "core"

urlpatterns = [
    path("landing/", show_main, name="landing"),
    path("terms/", views.policies, name="terms"),
    path("privacy/", views.policies, name="privacy"),
]
