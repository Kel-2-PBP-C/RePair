"""Exercise deployment configuration without reading local environment secrets."""

import os
from pathlib import Path
import runpy
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.core.handlers.asgi import ASGIHandler
from django.core.handlers.wsgi import WSGIHandler
from django.test import SimpleTestCase


class ConfigurationTests(SimpleTestCase):
    def load_settings(self, **environment):
        with patch.dict(os.environ, environment, clear=True), patch("dotenv.load_dotenv"):
            return runpy.run_path(str(Path(__file__).with_name("settings.py")))

    def test_local_defaults_use_sqlite_and_insecure_local_cookies(self):
        config = self.load_settings()
        self.assertFalse(config["PRODUCTION"])
        self.assertTrue(config["DEBUG"])
        self.assertTrue(config["SECRET_KEY"])
        self.assertEqual(config["DATABASES"]["default"]["ENGINE"], "django.db.backends.sqlite3")
        self.assertFalse(config["SESSION_COOKIE_SECURE"])
        self.assertFalse(config["CSRF_COOKIE_SECURE"])
        self.assertNotIn("SECURE_PROXY_SSL_HEADER", config)

    def test_production_requires_explicit_secret_key(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "DJANGO_SECRET_KEY"):
            self.load_settings(PRODUCTION="True")

    def test_production_loads_database_and_enables_secure_cookies(self):
        config = self.load_settings(
            PRODUCTION="TRUE", DJANGO_SECRET_KEY="test-deployment-secret",
            DB_NAME="repair", DB_USER="repair_user", DB_PASSWORD="test-db-password",
            DB_HOST="db.example.invalid", DB_PORT="5432", SCHEMA="repair_schema",
        )
        self.assertFalse(config["DEBUG"])
        self.assertEqual(config["SECRET_KEY"], "test-deployment-secret")
        self.assertEqual(config["DATABASES"]["default"], {
            "ENGINE": "django.db.backends.postgresql", "NAME": "repair",
            "USER": "repair_user", "PASSWORD": "test-db-password",
            "HOST": "db.example.invalid", "PORT": "5432",
            "OPTIONS": {"options": "-c search_path=repair_schema"},
        })
        self.assertTrue(config["SESSION_COOKIE_SECURE"])
        self.assertTrue(config["CSRF_COOKIE_SECURE"])

    def test_proxy_header_requires_explicit_opt_in(self):
        config = self.load_settings(DJANGO_TRUST_PROXY_HTTPS="True", DEBUG="False")
        self.assertFalse(config["DEBUG"])
        self.assertEqual(config["SECURE_PROXY_SSL_HEADER"], ("HTTP_X_FORWARDED_PROTO", "https"))

    def test_oauth_and_region_environment_values_are_trimmed(self):
        config = self.load_settings(
            GOOGLE_CLIENT_ID=" test-client ", GOOGLE_CLIENT_SECRET=" test-secret ",
            GOOGLE_REDIRECT_URI=" https://example.invalid/accounts/google/callback/ ",
            BOGORTECH_API_KEY=" test-key ", BOGORTECH_CA_BUNDLE=" /test/ca.pem ",
            GOOGLE_ONLY_AUTH="False", GOOGLE_ALLOW_REGISTRATION="False",
        )
        self.assertEqual(config["GOOGLE_CLIENT_ID"], "test-client")
        self.assertEqual(config["GOOGLE_CLIENT_SECRET"], "test-secret")
        self.assertEqual(config["GOOGLE_REDIRECT_URI"], "https://example.invalid/accounts/google/callback/")
        self.assertEqual(config["BOGORTECH_API_KEY"], "test-key")
        self.assertEqual(config["BOGORTECH_CA_BUNDLE"], "/test/ca.pem")
        self.assertFalse(config["GOOGLE_ONLY_AUTH"])
        self.assertFalse(config["GOOGLE_ALLOW_REGISTRATION"])

    def test_wsgi_and_asgi_entrypoints_initialize_handlers(self):
        from RePair.asgi import application as asgi_application
        from RePair.wsgi import application as wsgi_application

        self.assertIsInstance(asgi_application, ASGIHandler)
        self.assertIsInstance(wsgi_application, WSGIHandler)
