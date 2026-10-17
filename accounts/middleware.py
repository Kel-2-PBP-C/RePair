from django.shortcuts import redirect
from django.urls import Resolver404, resolve, reverse

from .models import GoogleIdentity, Profile
from . import google_auth


def google_profile_complete(user):
    profile = Profile.objects.filter(user=user).first()
    return bool(
        profile and (
            profile.onboarding_completed
            or (user.get_full_name().strip() and user.email
                and profile.domicile.strip() and profile.birth_date)
        )
    )


class GoogleProfileCompletionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not request.path.startswith('/admin/'):
            try:
                view_name = resolve(request.path_info).view_name
            except Resolver404:
                view_name = ''
            allowed = {
                'accounts:complete_profile', 'accounts:profile', 'accounts:settings',
                'accounts:logout', 'accounts:auth', 'accounts:login', 'accounts:register',
                'accounts:google_login', 'accounts:google_callback',
                'accounts:google_link',
                'accounts:region_search',
                'accounts:credentials', 'core:terms', 'core:privacy', 'home',
            }
            public = {
                'accounts:auth', 'accounts:login', 'accounts:register', 'accounts:logout',
                'accounts:google_login', 'accounts:google_callback', 'accounts:google_link',
                'accounts:credentials', 'core:terms', 'core:privacy', 'home',
            }
            is_google = GoogleIdentity.objects.filter(user=request.user).exists()
            review_pending = request.session.get(google_auth.PROFILE_REVIEW_KEY) == request.user.pk
            if is_google and view_name not in public and not google_auth.credentials_complete(request):
                request.session['google_credentials_next'] = request.get_full_path() if request.method == 'GET' else reverse('core:landing')
                return redirect('accounts:credentials')
            if (
                view_name not in allowed
                and is_google
                and (
                    review_pending
                    or not google_profile_complete(request.user)
                )
            ):
                if not review_pending or not request.session.get('google_profile_next'):
                    request.session['google_profile_next'] = request.get_full_path() if request.method == 'GET' else reverse('core:landing')
                return redirect('accounts:complete_profile')
        return self.get_response(request)
