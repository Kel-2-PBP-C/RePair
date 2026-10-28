import os
from pathlib import Path
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')
PRODUCTION = os.getenv('PRODUCTION', 'False').lower() == 'true'


SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', '')
if not SECRET_KEY and PRODUCTION:
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured('DJANGO_SECRET_KEY wajib diisi pada hosting.')
if not SECRET_KEY:
    # Fallback hanya untuk lokal; hosting wajib memiliki secret tetap.
    SECRET_KEY = 'django-insecure-n(gc2^gvo-wek=hiu4#099z%i&y$i7er#3%mjmfkc5so8f%bmc'


DEBUG = os.getenv('DEBUG', str(not PRODUCTION)).lower() == 'true'

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "rasya-azyan-repair.pws.cs.ui.ac.id"]


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core.apps.CoreConfig',
    'accounts.apps.AccountsConfig',
    'barter_details',
    'add_items',
    'profile_post',
    'keranjang',
    'main_page',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'accounts.middleware.GoogleProfileCompletionMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

#auto login dev env
if DEBUG and (BASE_DIR / 'barter_details' / 'dev_middleware.py').exists():
    MIDDLEWARE.append('barter_details.dev_middleware.DevAutoLoginMiddleware')

ROOT_URLCONF = 'RePair.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.navigation',
            ],
        },
    },
]

WSGI_APPLICATION = 'RePair.wsgi.application'


if PRODUCTION:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME'),
            'USER': os.getenv('DB_USER'),
            'PASSWORD': os.getenv('DB_PASSWORD'),
            'HOST': os.getenv('DB_HOST'),
            'PORT': os.getenv('DB_PORT'),
            'OPTIONS': {
                'options': f"-c search_path={os.getenv('SCHEMA', 'public')}"
            }
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
WHITENOISE_USE_FINDERS = True


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


LOGIN_URL = 'accounts:auth'
LOGIN_REDIRECT_URL = 'core:landing'
LOGOUT_REDIRECT_URL = 'accounts:auth'
REQUIRE_LOGIN_FOR_LANDING = True

GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '').strip()
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '').strip()
GOOGLE_REDIRECT_URI = os.getenv(
    'GOOGLE_REDIRECT_URI', 'http://localhost:8000/accounts/google/callback/'
).strip()
GOOGLE_ONLY_AUTH = os.getenv('GOOGLE_ONLY_AUTH', 'True').lower() == 'true'
PUBLIC_SUPPORT_EMAIL = os.getenv('PUBLIC_SUPPORT_EMAIL', '').strip()
BOGORTECH_API_KEY = os.getenv('BOGORTECH_API_KEY', '').strip()
BOGORTECH_CA_BUNDLE = os.getenv('BOGORTECH_CA_BUNDLE', '').strip()
GOOGLE_ALLOW_REGISTRATION = os.getenv('GOOGLE_ALLOW_REGISTRATION', 'True').lower() == 'true'
GOOGLE_LOGIN_TIMEOUT = 600
GOOGLE_REAUTH_TIMEOUT = 300
GOOGLE_ACCOUNT_LINK_TIMEOUT = 600
GOOGLE_ACCOUNT_LINK_MAX_ATTEMPTS = 5
GOOGLE_ACCOUNT_LINK_LOCKOUT = 900
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = PRODUCTION
CSRF_COOKIE_SECURE = PRODUCTION
CSRF_TRUSTED_ORIGINS = ['https://rasya-azyan-repair.pws.cs.ui.ac.id']
# Hanya aktifkan jika proxy tepercaya menimpa header ini.
if os.getenv('DJANGO_TRUST_PROXY_HTTPS', 'False').lower() == 'true':
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {'oauth_callback': {'()': 'accounts.logging.OAuthCallbackFilter'}},
    'loggers': {
        'django.server': {'filters': ['oauth_callback']},
        'django.request': {'filters': ['oauth_callback']},
        'authlib': {'level': 'WARNING'},
    },
}

# The post module keeps its own route, distinct from account settings.
NAVBAR_POSTS_URL_NAME = 'profile_post:show_posts'
