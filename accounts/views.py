from urllib.parse import urlencode, urlsplit
import logging
import time
import uuid
from datetime import timedelta

from authlib.integrations.base_client.errors import OAuthError
from joserfc.errors import JoseError
from requests.exceptions import RequestException
from django.conf import settings as django_settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login as auth_login, logout as auth_logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.backends.base import UpdateError
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, transaction
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST
from django.utils import timezone
from django.middleware.csrf import rotate_token

from .forms import DeactivateAccountForm, GoogleAccountLinkForm, GoogleCredentialsForm, GoogleProfileCompletionForm, LoginForm, PreferencesForm, ProfileForm, RegistrationForm
from .models import GoogleIdentity, Profile
from . import google_auth
from .deletion import permanently_delete_account
from .middleware import google_profile_complete

logger = logging.getLogger(__name__)


def _safe_next(request, target):
    auth_paths = {reverse(f"accounts:{name}") for name in ("auth", "login", "register", "logout", "google_login", "google_callback", "google_link", "credentials", "complete_profile")}
    if target and target.startswith('/') and not target.startswith('//') and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ) and urlsplit(target).path not in auth_paths:
        return target
    return reverse("core:landing")


def _next_url(request):
    target = request.POST.get("next") or request.GET.get("next", "")
    return _safe_next(request, target)


def _start_profile_review(request, next_url):
    request.session[google_auth.PROFILE_REVIEW_KEY] = request.user.pk
    request.session['google_profile_next'] = _safe_next(request, next_url)
    request.session.save()
    return redirect('accounts:complete_profile')


@require_http_methods(["GET", "HEAD"])
def entry(request):
    if django_settings.GOOGLE_ONLY_AUTH:
        return render(request, 'accounts/auth.html', {
            'next_url': reverse('core:landing'), 'google_configured': google_auth.configured(),
            'support_email': django_settings.PUBLIC_SUPPORT_EMAIL,
        })
    return redirect("core:landing" if request.user.is_authenticated else "accounts:auth")


def _auth(request, mode):
    next_url = _next_url(request)
    if request.user.is_authenticated:
        return redirect(next_url)
    form_class = RegistrationForm if mode == "register" else LoginForm
    kwargs = {"request": request} if mode == "login" else {}
    form = form_class(data=request.POST if request.method == "POST" else None, **kwargs)
    if request.method == "POST" and form.is_valid():
        if mode == "register":
            try:
                user = form.save()
            except IntegrityError:

                form.add_error("username", "Username ini sudah digunakan. Pilih username lain.")
            else:
                auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
                messages.success(request, "Akun berhasil dibuat. Selamat datang di RePair!")
                return redirect(next_url)
        else:
            auth_login(request, form.get_user())
            messages.success(request, "Berhasil masuk ke RePair.")
            return redirect(next_url)
    return render(request, "accounts/legacy_auth.html", {
        "auth_form": form, "auth_mode": mode, "next_url": next_url,
    })

@require_http_methods(["GET", "POST"])
def auth(request):
    if django_settings.GOOGLE_ONLY_AUTH:
        if request.user.is_authenticated:
            return redirect(_next_url(request))
        if request.method == 'POST':
            return HttpResponseBadRequest('Gunakan tombol Lanjutkan dengan Google.')
        return render(request, 'accounts/auth.html', {
            'next_url': _next_url(request), 'google_configured': google_auth.configured(),
            'support_email': django_settings.PUBLIC_SUPPORT_EMAIL,
        })
    mode = request.POST.get("mode") or request.GET.get("mode", "login")
    return _auth(request, "register" if mode == "register" else "login")


def _legacy_auth(request, mode):
    if django_settings.GOOGLE_ONLY_AUTH:
        if request.method == 'POST':
            return HttpResponseBadRequest('Gunakan tombol Lanjutkan dengan Google.')
        return redirect(f"{reverse('accounts:auth')}?{urlencode({'next': _next_url(request)})}")
    if request.method == "POST":
        return _auth(request, mode)
    query = {"mode": mode}
    if request.GET.get("next"):
        query["next"] = _next_url(request)
    return redirect(f"{reverse('accounts:auth')}?{urlencode(query)}")


@require_http_methods(["GET", "POST"])
def login(request):
    return _legacy_auth(request, "login")


@require_http_methods(["GET", "POST"])
def register(request):
    return _legacy_auth(request, "register")


@require_http_methods(['GET'])
def google_login(request):
    reauth = request.user.is_authenticated and request.GET.get('reauth') == '1'
    if request.user.is_authenticated and not reauth:
        return redirect(_next_url(request))
    try:
        return google_auth.begin_login(request, _next_url(request), reauthenticate=reauth)
    except google_auth.GoogleLoginError as error:
        messages.error(request, str(error))
    except (DatabaseError, UpdateError):
        return _google_unavailable(request)
    except (OAuthError, RequestException, ValueError):
        _log_google_failure('start')
        messages.error(request, 'Login Google belum dapat dimulai. Silakan coba lagi.')
    google_auth.clear_transaction(request)
    return redirect('accounts:auth')


def _log_google_failure(stage):

    logger.warning('Google login failed stage=%s correlation=%s', stage, uuid.uuid4().hex)


def _google_unavailable(request):
    # Jangan flush session saat storage gagal; SessionMiddleware tidak menyimpan respons 503.
    _log_google_failure('storage')
    request.session.clear()
    request.user = AnonymousUser()
    response = render(request, 'accounts/auth.html', {
        'next_url': reverse('core:landing'), 'google_configured': google_auth.configured(),
        'google_failure': 'Login belum dapat disimpan. Silakan coba lagi setelah layanan tersedia.',
    }, status=503)
    response.delete_cookie(
        django_settings.SESSION_COOKIE_NAME, path=django_settings.SESSION_COOKIE_PATH,
        domain=django_settings.SESSION_COOKIE_DOMAIN,
        samesite=django_settings.SESSION_COOKIE_SAMESITE,
    )
    return response


@require_http_methods(['GET'])
def google_callback(request):
    if request.user.is_authenticated and not request.session.get(google_auth.TRANSACTION_KEY):
        return redirect('core:landing')
    try:
        context = google_auth.consume_login(request)
        claims = google_auth.verified_claims(request, context)
        if context['user_id'] is not None:
            if not request.user.is_authenticated or request.user.pk != context['user_id'] or not GoogleIdentity.objects.filter(user=request.user, subject=claims['subject']).exists():
                raise google_auth.GoogleLoginError('Pilih akun Google yang terhubung ke akun RePair ini.')
            if not request.user.is_active:
                raise google_auth.GoogleLoginError('Akun ini tidak aktif. Hubungi pengelola aplikasi.')
            request.session.cycle_key()
        else:
            if request.user.is_authenticated:
                raise google_auth.GoogleLoginError('Akun sudah masuk. Mulai ulang verifikasi dari pengaturan akun.')
            try:
                user = google_auth.account_for_claims(claims)
            except google_auth.GoogleAccountLinkRequired as pending:
                google_auth.begin_account_link(request, pending.user_id, pending.claims, _safe_next(request, context['next']))
                google_auth.clear_transaction(request)
                request.session.save()
                return redirect('accounts:google_link')
            auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        request.session[google_auth.REAUTH_KEY] = {'user_id': request.user.pk, 'time': time.time()}
        google_auth.clear_transaction(request)
        next_url = _safe_next(request, context['next'])
        if context['user_id'] is None:
            request.session.pop(google_auth.CREDENTIALS_KEY, None)
            request.session.pop(google_auth.PROFILE_REVIEW_KEY, None)
            request.session['google_credentials_next'] = next_url
            request.session['google_credentials_failures'] = 0
            request.session.save()
            return redirect('accounts:credentials')
        # Simpan session sebelum mengembalikan respons login berhasil.
        if not google_profile_complete(request.user):
            request.session['google_profile_next'] = next_url
            request.session.save()
            messages.info(request, 'Lengkapi profil untuk mulai menggunakan RePair.')
            return redirect('accounts:complete_profile')
        request.session.save()
        messages.success(request, 'Berhasil masuk dengan Google.')
        return redirect(next_url)
    except google_auth.GoogleLoginError as error:
        messages.error(request, str(error))
    except (DatabaseError, UpdateError):
        return _google_unavailable(request)
    except (OAuthError, JoseError, RequestException, ValueError, KeyError):
        _log_google_failure('callback')
        messages.error(request, 'Login Google belum dapat diselesaikan. Silakan coba lagi.')
    google_auth.clear_transaction(request)
    return redirect('accounts:auth')


@require_http_methods(['GET', 'POST'])
def google_link(request):
    if request.user.is_authenticated:
        return redirect('accounts:profile')
    try:
        if request.method == 'POST' and request.POST.get('action') == 'cancel':
            google_auth.clear_account_link(request)
            messages.info(request, 'Penautan dibatalkan. Anda dapat memilih akun Google lain.')
            return redirect('accounts:auth')
        challenge = google_auth.get_account_link_challenge(request)
        if not challenge:
            google_auth.clear_account_link(request)
            messages.error(request, 'Sesi penautan kedaluwarsa atau belum dimulai. Gunakan tombol Google kembali.')
            return redirect('accounts:auth')
        form = GoogleAccountLinkForm(request.POST if request.method == 'POST' else None)
        if request.method == 'POST' and form.is_valid():
            try:
                user = google_auth.complete_account_link(request, form.cleaned_data['password'], form.cleaned_data['username'])
            except google_auth.GoogleLoginError as error:
                form.add_error(None, str(error))
            else:
                marker = request.session.pop(google_auth.LINK_SESSION_KEY, {})
                auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                request.session[google_auth.REAUTH_KEY] = {'user_id': user.pk, 'time': time.time()}
                google_auth.mark_credentials_complete(request)
                next_url = _safe_next(request, marker.get('next', ''))
                messages.success(request, 'Akun Google berhasil ditautkan. Periksa profil untuk melanjutkan.')
                return _start_profile_review(request, next_url)
        return render(request, 'accounts/link_google.html', {'link_form': form, 'google_email': challenge.email})
    except (DatabaseError, UpdateError):
        return _google_unavailable(request)


@login_required
@require_http_methods(['GET', 'POST'])
def credentials(request):
    if not GoogleIdentity.objects.filter(user=request.user).exists():
        return redirect('accounts:auth')
    if google_auth.credentials_complete(request):
        if request.session.get(google_auth.PROFILE_REVIEW_KEY) == request.user.pk:
            return redirect('accounts:complete_profile')
        return redirect(_safe_next(request, request.session.pop('google_credentials_next', '')))
    if not google_auth.recent_google_auth(request):
        auth_logout(request)
        messages.error(request, 'Verifikasi Google sudah kedaluwarsa. Lanjutkan dengan Google kembali.')
        return redirect('accounts:auth')
    setup = not request.user.has_usable_password()
    form = GoogleCredentialsForm(request.POST if request.method == 'POST' else None, user=request.user, setup=setup)
    try:
        if request.method == 'POST' and form.is_valid():
            User = get_user_model()
            failed = False
            blocked = False
            with transaction.atomic():
                user = User.objects.select_for_update().get(pk=request.user.pk)
                if not user.is_active or not GoogleIdentity.objects.filter(user=user).exists():
                    raise google_auth.GoogleLoginError('Akun ini belum dapat digunakan. Hubungi pengelola.')
                user_profile, _ = Profile.objects.select_for_update().get_or_create(user=user)
                if setup:
                    if user.has_usable_password():
                        raise google_auth.GoogleLoginError('Username dan password sudah dibuat. Mulai kembali dari Google.')
                    user.username = form.cleaned_data['username']
                    user.set_password(form.cleaned_data['password'])
                    user.save(update_fields=['username', 'password'])
                else:
                    now = timezone.now()
                    if not user_profile.credential_window_started or user_profile.credential_window_started <= now - timedelta(seconds=django_settings.GOOGLE_ACCOUNT_LINK_LOCKOUT):
                        user_profile.credential_failed_attempts = 0
                        user_profile.credential_window_started = now
                    if user_profile.credential_failed_attempts >= django_settings.GOOGLE_ACCOUNT_LINK_MAX_ATTEMPTS:
                        blocked = True
                    else:
                        user_profile.credential_failed_attempts += 1
                        user_profile.save(update_fields=['credential_failed_attempts', 'credential_window_started'])
                        password_valid = user.check_password(form.cleaned_data['password'])
                        failed = user.username != form.cleaned_data['username'] or not password_valid
                        if failed:
                            blocked = user_profile.credential_failed_attempts >= django_settings.GOOGLE_ACCOUNT_LINK_MAX_ATTEMPTS
                        else:
                            user_profile.credential_failed_attempts = 0
                            user_profile.save(update_fields=['credential_failed_attempts'])

            if blocked:
                auth_logout(request)
                messages.error(request, 'Terlalu banyak percobaan. Tunggu 15 menit, lalu lanjutkan dengan Google kembali.')
                return redirect('accounts:auth')
            if failed:
                form.add_error(None, 'Username atau password RePair tidak benar.')
            else:
                request.user = user
                update_session_auth_hash(request, user)
                rotate_token(request)
                google_auth.mark_credentials_complete(request)
                next_url = _safe_next(request, request.session.pop('google_credentials_next', ''))
                return _start_profile_review(request, next_url)
        return render(request, 'accounts/credentials.html', {
            'credentials_form': form, 'credentials_mode': 'create' if setup else 'login',
        })
    except IntegrityError:
        form.add_error('username', 'Username ini sudah digunakan. Pilih username lain.')
        return render(request, 'accounts/credentials.html', {
            'credentials_form': form, 'credentials_mode': 'create' if setup else 'login',
        })
    except google_auth.GoogleLoginError as error:
        auth_logout(request)
        messages.error(request, str(error))
        return redirect('accounts:auth')
    except (DatabaseError, UpdateError):
        return _google_unavailable(request)


@login_required
@require_http_methods(['GET', 'POST'])
def complete_profile(request):
    if not GoogleIdentity.objects.filter(user=request.user).exists():
        return redirect('accounts:profile')
    user_profile, _ = Profile.objects.get_or_create(user=request.user)
    if request.method == 'POST' and request.POST.get('action') == 'skip':
        user_profile.onboarding_completed = True
        user_profile.save(update_fields=['onboarding_completed'])
        request.session.pop(google_auth.PROFILE_REVIEW_KEY, None)
        return redirect(_safe_next(request, request.session.pop('google_profile_next', '')))
    form = GoogleProfileCompletionForm(
        request.POST if request.method == 'POST' else None,
        user=request.user, instance=user_profile,
    )
    if request.method == 'POST' and form.is_valid():
        try:
            form.save()
        except IntegrityError:
            form.add_error('username', 'Username ini sudah digunakan oleh akun lain.')
        else:
            google_auth.mark_credentials_complete(request)
            request.session.pop(google_auth.PROFILE_REVIEW_KEY, None)
            messages.success(request, 'Profil berhasil dilengkapi. Selamat datang di RePair!')
            return redirect(_safe_next(request, request.session.pop('google_profile_next', '')))
    return render(request, 'accounts/complete_profile.html', {'completion_form': form})


@login_required
@require_http_methods(["GET", "POST"])
def profile(request):
    user_profile, _ = Profile.objects.get_or_create(user=request.user)
    action = request.POST.get("action", "profile") if request.method == "POST" else None
    is_google_account = GoogleIdentity.objects.filter(user=request.user).exists()
    if action == 'password' and not request.user.has_usable_password():
        return HttpResponseBadRequest('Keamanan akun ini dikelola melalui Google.')
    if action is not None and action not in {"profile", "preferences", "password", "deactivate", "delete"}:
        return HttpResponseBadRequest("Aksi pengaturan tidak dikenal.")
    profile_form = ProfileForm(
        request.POST if action == "profile" else None, user=request.user, instance=user_profile
    )
    preferences_form = PreferencesForm(
        request.POST if action == "preferences" else None, instance=user_profile
    )
    password_form = PasswordChangeForm(
        user=request.user, data=request.POST if action == "password" else None
    )
    deactivate_form = DeactivateAccountForm(
        request.POST if action in {"deactivate", "delete"} else None, user=request.user,
        google_authenticated=google_auth.recent_google_auth(request),
    )
    selected_form = {
        "profile": profile_form, "preferences": preferences_form,
        "password": password_form, "deactivate": deactivate_form, "delete": deactivate_form,
    }.get(action)
    if selected_form is not None and selected_form.is_valid():
        if action in {"deactivate", "delete"}:
            try:
                permanently_delete_account(
                    user_id=request.user.pk,
                    password=deactivate_form.cleaned_data.get("password", ""),
                    google_authenticated=google_auth.recent_google_auth(request),
                    session_key=request.session.session_key,
                )
            except ValidationError as error:
                deactivate_form.add_error(None, error)
            except (DatabaseError, get_user_model().DoesNotExist):
                deactivate_form.add_error(None, "Akun belum dapat dihapus. Silakan coba lagi.")
            else:
                auth_logout(request)
                messages.success(
                    request,
                    "Akun dan data milikmu berhasil dihapus permanen. Kamu dapat mendaftar lagi dengan email yang sama.",
                    extra_tags="account-deleted",
                )
                return redirect("home")
        elif action == "password":
            try:
                with transaction.atomic():
                    user = get_user_model().objects.select_for_update().get(pk=request.user.pk)
                    if not user.is_active:
                        raise get_user_model().DoesNotExist
                    if not user.check_password(password_form.cleaned_data["old_password"]):
                        password_form.add_error("old_password", ValidationError(
                            password_form.error_messages["password_incorrect"], code="password_incorrect",
                        ))
                    else:
                        user.set_password(password_form.cleaned_data["new_password1"])
                        # UPDATE mencegah form lama membuat ulang akun yang sudah dihapus.
                        user.save(update_fields=["password"])
            except get_user_model().DoesNotExist:
                auth_logout(request)
                return redirect("home")
            except DatabaseError:
                password_form.add_error(None, "Password belum dapat diperbarui. Silakan coba lagi.")
            else:
                if not password_form.errors:
                    request.user = user
                    update_session_auth_hash(request, user)
                    if is_google_account:
                        google_auth.mark_credentials_complete(request)
                    messages.success(request, "Password berhasil diubah.")
        elif action == "preferences":
            preferences_form.save()
            messages.success(request, "Preferensi berhasil disimpan.")
        elif action == "profile":
            try:
                profile_form.save()
            except IntegrityError:
                profile_form.add_error("username", "Username ini sudah digunakan oleh akun lain.")
            else:
                messages.success(request, "Profil berhasil diperbarui.")
        if action not in {"deactivate", "delete"} and not selected_form.errors:
            section = "profile" if action == "profile" else "settings"
            return redirect(f"{reverse('accounts:profile')}#{section}")
    return render(request, "accounts/profile_settings.html", {
        "profile": user_profile, "profile_form": profile_form,
        "preferences_form": preferences_form, "password_form": password_form,
        "deactivate_form": deactivate_form,
        "active_section": "settings" if action in {"preferences", "password", "deactivate", "delete"} else "profile",
        'is_google_account': is_google_account,
        'can_change_password': request.user.has_usable_password(),
        'google_reauth_recent': google_auth.recent_google_auth(request),
        'delete_requires_google_reauth': deactivate_form.requires_google_reauth,
        'profile_stats': {'items_exchanged': None, 'reputation_percent': None},
        'profile_initials': ''.join(
            part[0].upper() for part in request.user.get_full_name().split()[:2]
        ) or request.user.get_username()[:2].upper(),
        'google_reauth_url': f"{reverse('accounts:google_login')}?{urlencode({'reauth': '1', 'next': reverse('accounts:profile') + '#account-status'})}",
    })


@login_required
@require_http_methods(["GET"])
def settings(request):
    return redirect(f"{reverse('accounts:profile')}#settings")


@require_POST
def logout(request):
    auth_logout(request)
    messages.success(request, "Kamu telah keluar dari akun.")
    return redirect("accounts:auth")
