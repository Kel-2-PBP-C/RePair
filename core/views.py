from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_safe


@require_GET
def landing(request):
    if getattr(settings, "REQUIRE_LOGIN_FOR_LANDING", False):
        if not getattr(getattr(request, "user", None), "is_authenticated", False):
            return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)
    return render(request, "core/landing.html")


@require_safe
def policies(request):
    close_url = request.GET.get('next', '')
    if not (
        close_url.startswith('/') and not close_url.startswith('//')
        and url_has_allowed_host_and_scheme(close_url, allowed_hosts={request.get_host()}, require_https=request.is_secure())
        and close_url.split('?', 1)[0].split('#', 1)[0] not in {reverse('core:terms'), reverse('core:privacy')}
    ):
        close_url = reverse('home')
    is_privacy = getattr(request.resolver_match, 'url_name', '') == 'privacy'
    template = 'core/privacy.html' if is_privacy else 'core/policies.html'
    return render(request, template, {
        'close_url': close_url,
        'support_email': getattr(settings, 'PUBLIC_SUPPORT_EMAIL', ''),
    })
