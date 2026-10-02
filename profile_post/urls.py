from django.urls import path

from profile_post import views


app_name = "profile_post"

urlpatterns = [
    path("", views.show_profile, name="show_profile"),
]