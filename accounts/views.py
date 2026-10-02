from urllib.parse import urlencode, urlsplit

from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.db import IntegrityError
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST

from .forms import DeactivateAccountForm, LoginForm, PreferencesForm, ProfileForm, RegistrationForm
from .models import Profile


def _next_url(request):
    target = request.POST.get("next") or request.GET.get("next", "")
    auth_paths = {reverse(f"accounts:{name}") for name in ("auth", "login", "register", "logout")}
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ) and urlsplit(target).path not in auth_paths:
        return target
    return reverse("core:landing")


@require_http_methods(["GET"])
def entry(request):
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
                # A concurrent username registration must leave the form usable.
                form.add_error("username", "Username ini sudah digunakan. Pilih username lain.")
            else:
                auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
                messages.success(request, "Akun berhasil dibuat. Selamat datang di RePair!")
                return redirect(next_url)
        else:
            auth_login(request, form.get_user())
            messages.success(request, "Berhasil masuk ke RePair.")
            return redirect(next_url)
    return render(request, "accounts/auth.html", {
        "auth_form": form, "auth_mode": mode, "next_url": next_url,
    })


@require_http_methods(["GET", "POST"])
def auth(request):
    mode = request.POST.get("mode") or request.GET.get("mode", "login")
    return _auth(request, "register" if mode == "register" else "login")


def _legacy_auth(request, mode):
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


@login_required
@require_http_methods(["GET", "POST"])
def profile(request):
    user_profile, _ = Profile.objects.get_or_create(user=request.user)
    action = request.POST.get("action", "profile") if request.method == "POST" else None
    if action is not None and action not in {"profile", "preferences", "password", "deactivate"}:
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
        request.POST if action == "deactivate" else None, user=request.user
    )
    selected_form = {
        "profile": profile_form, "preferences": preferences_form,
        "password": password_form, "deactivate": deactivate_form,
    }.get(action)
    if selected_form is not None and selected_form.is_valid():
        if action == "deactivate":
            request.user.is_active = False
            request.user.save(update_fields=["is_active"])
            auth_logout(request)
            messages.success(request, "Akun telah dinonaktifkan.")
            return redirect("accounts:auth")
        if action == "password":
            user = password_form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Password berhasil diubah.")
        elif action == "preferences":
            preferences_form.save()
            messages.success(request, "Preferensi berhasil disimpan.")
        else:
            profile_form.save()
            messages.success(request, "Profil berhasil diperbarui.")
        section = "profile" if action == "profile" else "settings"
        return redirect(f"{reverse('accounts:profile')}#{section}")
    return render(request, "accounts/profile_settings.html", {
        "profile": user_profile, "profile_form": profile_form,
        "preferences_form": preferences_form, "password_form": password_form,
        "deactivate_form": deactivate_form,
        "active_section": "settings" if action in {"preferences", "password", "deactivate"} else "profile",
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
