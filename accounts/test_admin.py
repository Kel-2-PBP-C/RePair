from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import GoogleIdentity


class GoogleIdentityAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser(
            username="admin-test", email="admin@example.com", password="AdminTest!9204"
        )
        cls.identity = GoogleIdentity.objects.create(
            user=cls.staff, subject="admin-test-subject", email="admin@example.com"
        )

    def setUp(self):
        self.client.force_login(self.staff)

    def test_even_superuser_cannot_create_identity_through_admin(self):
        url = reverse("admin:accounts_googleidentity_add")
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, {}).status_code, 403)
        self.assertEqual(GoogleIdentity.objects.count(), 1)

    def test_even_superuser_cannot_delete_identity_through_admin(self):
        url = reverse("admin:accounts_googleidentity_delete", args=[self.identity.pk])
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, {"post": "yes"}).status_code, 403)
        self.assertTrue(GoogleIdentity.objects.filter(pk=self.identity.pk).exists())

    def test_identity_can_be_inspected_without_editable_identity_fields(self):
        response = self.client.get(reverse("admin:accounts_googleidentity_change", args=[self.identity.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.identity.subject)
        self.assertEqual(response.context["adminform"].form.fields, {})
        self.assertNotIn("delete_selected", admin.site._registry[GoogleIdentity].get_actions(response.wsgi_request))
