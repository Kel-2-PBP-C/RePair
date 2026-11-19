from django.conf import settings
from django.urls import NoReverseMatch, reverse


def _optional_url(*names):
    for name in names:
        if not name:
            continue
        try:
            return reverse(name)
        except NoReverseMatch:
            continue
    return None


def _is_active(request, url):
    return bool(url) and (
        request.path == url
        or (url != "/" and request.path.startswith(url.rstrip("/") + "/"))
    )


def navigation(request):
    home_url = _optional_url("core:landing")
    cart_url = _optional_url(
        getattr(settings, "NAVBAR_CART_URL_NAME", None),
        "keranjang",
        "keranjang:keranjang",
        "cart:index",
    )
    posts_url = _optional_url(
        getattr(settings, "NAVBAR_POSTS_URL_NAME", None),
        "daftar_post:show_daftar_post",
        "daftar_post:show_posts",
        "posts:my_posts",
        "post_list:show_posts",
        "profile_post:show_posts",
    )
    profile_url = _optional_url("accounts:profile")
    login_url = _optional_url("accounts:auth", "accounts:login")
    authenticated = bool(getattr(getattr(request, "user", None), "is_authenticated", False))
    settings_url = profile_url if authenticated else login_url
    account_active = _is_active(request, profile_url)
    match = getattr(request, "resolver_match", None)
    if match and match.namespace == "accounts":
        account_active = match.url_name in {"profile", "settings"}

    return {
        "navigation": {
            "home_url": home_url,
            "items": [
                {"key": "home", "label": "Home", "url": home_url,
                 "active": _is_active(request, home_url), "icon": "img/home_filled.png"},
                {"key": "cart", "label": "Cart", "url": cart_url,
                 "active": _is_active(request, cart_url), "icon": "img/shopping_cart.png"},
                {"key": "posts", "label": "Posts", "url": posts_url,
                 "active": _is_active(request, posts_url), "icon": "img/insert_photo.png"},
                {"key": "settings", "label": "Settings", "url": settings_url,
                 "active": account_active, "icon": "img/settings.png"},
            ],
            "profile_url": profile_url,
            "account_active": account_active,
            "login_url": login_url,
            "register_url": _optional_url("accounts:register"),
            "logout_url": _optional_url("accounts:logout"),
        }
    }
