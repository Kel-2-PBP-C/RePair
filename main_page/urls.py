from django.urls import path
from main_page.views import show_main

app_name = "main_page"

urlpatterns = [
    path("", show_main, name="show_main"),
]