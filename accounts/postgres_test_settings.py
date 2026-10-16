"""Konfigurasi PostgreSQL uji, terpisah dari database production."""
import os
from django.core.exceptions import ImproperlyConfigured

from .test_settings import *  # noqa: F403

test_database_name = os.getenv('TEST_POSTGRES_NAME', '')
if not test_database_name.startswith('test_'):
    raise ImproperlyConfigured('TEST_POSTGRES_NAME wajib menunjuk database uji terpisah dengan awalan test_.')
if not os.getenv('TEST_POSTGRES_USER') or not os.getenv('TEST_POSTGRES_HOST'):
    raise ImproperlyConfigured('Isi TEST_POSTGRES_USER dan TEST_POSTGRES_HOST untuk database uji terpisah.')

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': test_database_name,
        'USER': os.getenv('TEST_POSTGRES_USER'),
        'PASSWORD': os.getenv('TEST_POSTGRES_PASSWORD', ''),
        'HOST': os.getenv('TEST_POSTGRES_HOST'),
        'PORT': os.getenv('TEST_POSTGRES_PORT', '5432'),
        'TEST': {'NAME': test_database_name},
    },
}
