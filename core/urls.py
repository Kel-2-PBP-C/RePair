from django.urls import path

from main_page.views import show_main

app_name = "core"

urlpatterns = [
    path("landing/", show_main, name="landing"),
]
