"""Konfigurasi test dengan database terpisah dari production."""

import os

os.environ["PRODUCTION"] = "False"

from RePair.settings import *  # noqa: F403, E402

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Test defaults must not depend on the developer's .env or use real API keys.
SECRET_KEY = "repair-tests-only-not-for-production"
GOOGLE_CLIENT_ID = ""
GOOGLE_CLIENT_SECRET = ""
GOOGLE_REDIRECT_URI = "http://localhost:8000/accounts/google/callback/"
GOOGLE_ONLY_AUTH = True
GOOGLE_ALLOW_REGISTRATION = True
BOGORTECH_API_KEY = ""
BOGORTECH_CA_BUNDLE = ""
PUBLIC_SUPPORT_EMAIL = ""
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_PROXY_SSL_HEADER = None
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
