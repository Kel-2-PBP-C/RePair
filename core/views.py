from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import render
from django.views.decorators.http import require_GET


@require_GET
def landing(request):
    """Keep a stable destination until the main-page module is integrated."""
    if getattr(settings, "REQUIRE_LOGIN_FOR_LANDING", False):
        if not getattr(getattr(request, "user", None), "is_authenticated", False):
            return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)
    return render(request, "core/landing.html")
