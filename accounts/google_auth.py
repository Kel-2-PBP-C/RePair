import hashlib
import math
import secrets
import time
import uuid
from datetime import timedelta
from functools import lru_cache
from urllib.parse import urlsplit

from authlib.integrations.django_client import OAuth
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import GoogleAccountLinkChallenge, GoogleIdentity, GoogleLoginAttempt, Profile

TRANSACTION_KEY = 'google_login_transaction'
REAUTH_KEY = 'google_recent_auth'
LINK_SESSION_KEY = 'google_account_link'
CREDENTIALS_KEY = 'google_credentials_complete'
PROFILE_REVIEW_KEY = 'google_profile_review_pending'


class GoogleLoginError(Exception):
    """Pesan aman untuk pengguna tanpa token atau detail provider."""


class GoogleAccountLinkRequired(GoogleLoginError):
    def __init__(self, user_id, claims):
        super().__init__('Verifikasi akun RePair lama untuk menautkan Google.')
        self.user_id = user_id
        self.claims = claims


def configured():
    parsed = urlsplit(settings.GOOGLE_REDIRECT_URI)
    return bool(
        settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET
        and parsed.hostname and not parsed.username and not parsed.password
        and not parsed.query and not parsed.fragment
        and parsed.path == '/accounts/google/callback/'
        and (parsed.scheme == 'https' or (
            not settings.PRODUCTION and parsed.scheme == 'http'
            and parsed.hostname in {'localhost', '127.0.0.1'}
        ))
    )


@lru_cache(maxsize=8)
def _client(client_id, client_secret):
    oauth = OAuth()
    return oauth.register(
        'google', client_id=client_id, client_secret=client_secret,
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={
            'scope': 'openid email profile', 'code_challenge_method': 'S256',
            'default_timeout': 10,
        },
    )


def get_google_client():
    return _client(settings.GOOGLE_CLIENT_ID, settings.GOOGLE_CLIENT_SECRET)


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def clear_transaction(request):
    request.session.pop(TRANSACTION_KEY, None)
    for key in list(request.session.keys()):
        if key.startswith('_state_google_'):
            request.session.pop(key, None)


def begin_login(request, next_url, reauthenticate=False):
    if not configured():
        raise GoogleLoginError('Login Google belum dikonfigurasi. Hubungi pengelola aplikasi.')
    if not request.session.session_key:
        request.session.create()
    clear_account_link(request)
    now = timezone.now()
    session_digest = digest(request.session.session_key)
    GoogleLoginAttempt.objects.filter(expires_at__lt=now).delete()
    if GoogleLoginAttempt.objects.filter(session_digest=session_digest).count() >= 10:
        raise GoogleLoginError('Terlalu banyak percobaan login. Tunggu 10 menit lalu coba lagi.')
    clear_transaction(request)
    if reauthenticate:
        request.session.pop(REAUTH_KEY, None)
    state, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(32)

    response = get_google_client().authorize_redirect(
        request, settings.GOOGLE_REDIRECT_URI, state=state, nonce=nonce,
        prompt='select_account',
    )
    GoogleLoginAttempt.objects.create(
        state_digest=digest(state), session_digest=session_digest,
        expires_at=now + timedelta(seconds=settings.GOOGLE_LOGIN_TIMEOUT),
    )
    request.session[TRANSACTION_KEY] = {
        'state': state, 'nonce': nonce, 'started': time.time(), 'next': next_url,
        'user_id': request.user.pk if reauthenticate else None,
    }
    return response


def consume_login(request):
    context = request.session.get(TRANSACTION_KEY)
    state = request.GET.get('state', '')
    if (
        not isinstance(context, dict) or not state or not state.isascii() or len(state) > 255
        or not secrets.compare_digest(state, context.get('state', ''))
        or not request.session.session_key
    ):
        raise GoogleLoginError('Sesi login tidak valid. Mulai lagi dari tombol Google.')
    now = timezone.now()
    # Hanya satu callback boleh menghabiskan transaksi.
    consumed = GoogleLoginAttempt.objects.filter(
        state_digest=digest(state), session_digest=digest(request.session.session_key),
        consumed_at__isnull=True, expires_at__gt=now,
    ).update(consumed_at=now)
    if consumed != 1:
        raise GoogleLoginError('Sesi login sudah dipakai atau kedaluwarsa. Silakan coba lagi.')
    request.session.pop(TRANSACTION_KEY, None)
    if request.GET.get('error'):
        message = 'Login Google dibatalkan.' if request.GET['error'] == 'access_denied' else 'Google belum dapat menyelesaikan login. Silakan coba lagi.'
        raise GoogleLoginError(message)
    if not request.GET.get('code'):
        raise GoogleLoginError('Google tidak mengirim hasil login. Silakan coba lagi.')
    return context


def verified_claims(request, context):
    # Authlib memverifikasi tanda tangan, masa berlaku, issuer, audience, dan nonce.
    token = get_google_client().authorize_access_token(
        request, leeway=60,
        claims_options={
            'iss': {'essential': True, 'values': ['https://accounts.google.com', 'accounts.google.com']},
            'aud': {'essential': True, 'values': [settings.GOOGLE_CLIENT_ID]},
        },
    )
    claims = token.get('userinfo')
    if not claims or not token.get('id_token'):
        raise GoogleLoginError('Identitas Google tidak dapat diverifikasi. Silakan coba lagi.')
    nonce = claims.get('nonce')
    if not isinstance(nonce, str) or not nonce.isascii() or not secrets.compare_digest(nonce, context['nonce']):
        raise GoogleLoginError('Identitas Google tidak dapat diverifikasi. Silakan coba lagi.')
    subject, email = claims.get('sub'), claims.get('email')
    if not isinstance(subject, str) or not subject or len(subject) > 255 or not subject.isascii():
        raise GoogleLoginError('Identitas Google tidak lengkap. Silakan gunakan akun lain.')
    if not isinstance(email, str) or claims.get('email_verified') is not True:
        raise GoogleLoginError('Gunakan akun Google dengan email yang sudah terverifikasi.')
    email = email.strip().lower()
    try:
        validate_email(email)
        if len(email) > 254:
            raise ValidationError('Email terlalu panjang.')
    except ValidationError:
        raise GoogleLoginError('Email Google tidak dapat digunakan. Silakan gunakan akun lain.') from None
    return {'subject': subject, 'email': email, 'name': claims.get('name') or ''}


def _active(user):
    if not user.is_active:
        raise GoogleLoginError('Akun ini tidak aktif. Hubungi pengelola aplikasi.')
    return user


def account_for_claims(claims):
    User = get_user_model()
    try:
        with transaction.atomic():
            identity = GoogleIdentity.objects.select_related('user').filter(subject=claims['subject']).first()
            if identity:
                # Identitas memakai subject Google; email tidak boleh menautkan akun otomatis.
                return _active(identity.user)
            matches = list(User.objects.filter(email__iexact=claims['email'])[:2])
            if matches:
                if len(matches) == 1 and _link_eligible(matches[0], claims):
                    raise GoogleAccountLinkRequired(matches[0].pk, claims)
                raise GoogleLoginError('Login belum dapat ditautkan. Hubungi pengelola untuk memverifikasi dan menautkan akun lama.')
            if not settings.GOOGLE_ALLOW_REGISTRATION:
                raise GoogleLoginError('Pendaftaran akun baru belum dibuka. Hubungi pengelola aplikasi.')
            name = claims['name'] if isinstance(claims['name'], str) else ''
            user = User.objects.create_user(
                username=f'google_{uuid.uuid4().hex}', email=claims['email'],
                first_name=name.strip()[:150], password=None,
            )
            Profile.objects.create(user=user)
            GoogleIdentity.objects.create(user=user, subject=claims['subject'], email=claims['email'])
            return user
    except IntegrityError:

        identity = GoogleIdentity.objects.select_related('user').filter(subject=claims['subject']).first()
        if identity:
            return _active(identity.user)
        raise GoogleLoginError('Akun belum dapat disimpan. Silakan coba lagi atau hubungi pengelola.') from None


def recent_google_auth(request):
    marker = request.session.get(REAUTH_KEY, {})
    stamp = marker.get('time') if isinstance(marker, dict) else None
    return bool(
        isinstance(marker, dict) and marker.get('user_id') == request.user.pk
        and isinstance(stamp, (int, float)) and not isinstance(stamp, bool)
        and math.isfinite(stamp)
        and 0 <= time.time() - stamp < settings.GOOGLE_REAUTH_TIMEOUT
    )


def mark_credentials_complete(request):
    request.session[CREDENTIALS_KEY] = {
        'user_id': request.user.pk, 'auth_hash': request.user.get_session_auth_hash(),
    }


def credentials_complete(request):
    marker = request.session.get(CREDENTIALS_KEY, {})
    stamp = marker.get('auth_hash') if isinstance(marker, dict) else None
    return bool(
        request.user.is_authenticated and isinstance(marker, dict)
        and marker.get('user_id') == request.user.pk
        and isinstance(stamp, str) and stamp.isascii()
        and secrets.compare_digest(stamp, request.user.get_session_auth_hash())
    )


def _link_eligible(user, claims):
    User = get_user_model()
    return bool(
        user.is_active and user.has_usable_password()
        and user.email.strip().lower() == claims['email']
        and not User.objects.filter(email__iexact=claims['email']).exclude(pk=user.pk).exists()
        and not GoogleIdentity.objects.filter(user=user).exists()
        and not GoogleIdentity.objects.filter(subject=claims['subject']).exists()
        and not GoogleIdentity.objects.filter(email__iexact=claims['email']).exists()
    )


def _link_filters(request):
    marker = request.session.get(LINK_SESSION_KEY, {})
    key = marker.get('key') if isinstance(marker, dict) else None
    if not isinstance(key, str) or not key or not key.isascii() or len(key) > 255 or not request.session.session_key:
        return None
    return {'token_digest': digest(key), 'session_digest': digest(request.session.session_key)}


def clear_account_link(request):
    filters = _link_filters(request)
    if filters:
        GoogleAccountLinkChallenge.objects.filter(**filters, consumed_at__isnull=True).update(consumed_at=timezone.now())
    request.session.pop(LINK_SESSION_KEY, None)


def get_account_link_challenge(request):
    filters = _link_filters(request)
    if filters:
        return GoogleAccountLinkChallenge.objects.filter(
            **filters, consumed_at__isnull=True, expires_at__gt=timezone.now(),
        ).first()
    return None


def _reset_link_window(challenge, now):
    if challenge.window_started <= now - timedelta(seconds=settings.GOOGLE_ACCOUNT_LINK_LOCKOUT):
        challenge.failed_attempts = 0
        challenge.window_started = now


def begin_account_link(request, user_id, claims, next_url):
    User = get_user_model()
    request.session.cycle_key()
    key = secrets.token_urlsafe(32)
    now = timezone.now()
    with transaction.atomic():
        user = User.objects.select_for_update().filter(pk=user_id).first()
        if user is None or not _link_eligible(user, claims):
            raise GoogleLoginError('Akun belum dapat ditautkan. Hubungi pengelola aplikasi.')
        challenge = GoogleAccountLinkChallenge.objects.select_for_update().filter(user=user).first()
        if challenge:
            _reset_link_window(challenge, now)
            if challenge.failed_attempts >= settings.GOOGLE_ACCOUNT_LINK_MAX_ATTEMPTS:
                raise GoogleLoginError('Terlalu banyak percobaan kata sandi. Tunggu 15 menit sebelum mencoba lagi.')
        else:
            challenge = GoogleAccountLinkChallenge(user=user, window_started=now)
        challenge.token_digest = digest(key)
        challenge.session_digest = digest(request.session.session_key)
        challenge.subject = claims['subject']
        challenge.email = claims['email']
        challenge.expires_at = now + timedelta(seconds=settings.GOOGLE_ACCOUNT_LINK_TIMEOUT)
        challenge.consumed_at = None
        challenge.save()
    request.session[LINK_SESSION_KEY] = {'key': key, 'next': next_url}


def complete_account_link(request, password, username=None):
    User = get_user_model()
    filters = _link_filters(request)
    snapshot = GoogleAccountLinkChallenge.objects.filter(**filters).first() if filters else None
    if not snapshot:
        raise GoogleLoginError('Sesi penautan tidak valid. Mulai lagi dari tombol Google.')
    error = None
    user = None
    try:
        with transaction.atomic():
            # Urutan lock selalu User, lalu challenge.
            user = User.objects.select_for_update().get(pk=snapshot.user_id)
            challenge = GoogleAccountLinkChallenge.objects.select_for_update().filter(user=user, **filters).first()
            now = timezone.now()
            if not challenge or challenge.consumed_at or challenge.expires_at <= now:
                error = 'Sesi penautan sudah dipakai atau kedaluwarsa. Mulai lagi dari tombol Google.'
            elif not _link_eligible(user, {'email': challenge.email, 'subject': challenge.subject}):
                challenge.consumed_at = now
                challenge.save(update_fields=['consumed_at'])
                error = 'Akun belum dapat ditautkan. Hubungi pengelola aplikasi.'
            else:
                _reset_link_window(challenge, now)
                if challenge.failed_attempts >= settings.GOOGLE_ACCOUNT_LINK_MAX_ATTEMPTS:
                    error = 'Terlalu banyak percobaan kata sandi. Tunggu 15 menit sebelum mencoba lagi.'
                else:
                    # Kegagalan password tetap disimpan saat transaksi selesai.
                    challenge.failed_attempts += 1
                    challenge.save(update_fields=['failed_attempts', 'window_started'])
                    password_valid = user.check_password(password)
                    if username != user.get_username() or not password_valid:
                        error = 'Username atau password RePair lama tidak benar. Coba lagi atau hubungi pengelola.'
                    else:

                        GoogleIdentity.objects.create(user=user, subject=challenge.subject, email=challenge.email)
                        challenge.consumed_at = now
                        challenge.failed_attempts = 0
                        challenge.save(update_fields=['consumed_at', 'failed_attempts'])
    except IntegrityError:
        raise GoogleLoginError('Penautan berbenturan dengan identitas lain. Mulai lagi dari tombol Google.') from None
    except User.DoesNotExist:
        raise GoogleLoginError('Akun belum dapat ditautkan. Hubungi pengelola aplikasi.') from None
    if error:
        raise GoogleLoginError(error)
    return user
