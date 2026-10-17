from django.http import HttpResponse
from django.urls import include, path


def placeholder(request):
    return HttpResponse("Test route")


account_patterns = [
    path("auth/", placeholder, name="auth"),
    path("login/", placeholder, name="login"),
    path("register/", placeholder, name="register"),
    path("profile/", placeholder, name="profile"),
    path("settings/", placeholder, name="settings"),
    path("logout/", placeholder, name="logout"),
]

post_patterns = [path("", placeholder, name="show_posts")]
forum_patterns = [
    path("", placeholder, name="show_forum"),
    path("topics/<int:pk>/", placeholder, name="topic"),
]

urlpatterns = [
    path("", include("core.urls")),
    path("accounts/", include((account_patterns, "accounts"))),
    path("keranjang/", placeholder, name="keranjang"),
    path("posts/", include((post_patterns, "daftar_post"))),
    path("forum/", include((forum_patterns, "forum"))),
    path("discussion/", placeholder, name="custom_forum"),
    path("my-posts/", placeholder, name="custom_post_list"),
]
