from django.test import SimpleTestCase, override_settings
from django.urls import reverse


@override_settings(GOOGLE_CLIENT_ID='', GOOGLE_CLIENT_SECRET='', PUBLIC_SUPPORT_EMAIL='')
class PublicPolicyTests(SimpleTestCase):
    def test_privacy_is_a_dedicated_public_page_without_oauth_configuration(self):
        response = self.client.get(reverse('core:privacy'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/privacy.html')
        self.assertContains(response, '<h1 id="privacy-title" class="brand-legal-title">Kebijakan Privasi RePair</h1>', html=True)
        self.assertContains(response, '16 Oktober 2026')
        for anchor in (
            'privacy-google-data', 'privacy-account-data', 'privacy-purpose',
            'privacy-sharing', 'privacy-storage', 'privacy-rights', 'privacy-delete',
            'privacy-contact',
        ):
            with self.subTest(section=anchor):
                self.assertContains(response, f'id="{anchor}"')
        self.assertContains(response, 'basis data aktif')
        self.assertContains(response, 'salinan cadangan')
        self.assertNotContains(response, 'YOUR_EMAIL')

    @override_settings(PUBLIC_SUPPORT_EMAIL='support@example.org')
    def test_privacy_has_the_configured_support_contact(self):
        response = self.client.get(reverse('core:privacy'))
        self.assertContains(response, 'href="mailto:support@example.org"')

    def test_terms_remains_available_and_links_to_full_privacy_policy(self):
        response = self.client.get(reverse('core:terms'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/policies.html')
        self.assertContains(response, 'href="/privacy/">Kebijakan Privasi RePair</a>')

    def test_crawlers_can_request_head_without_login(self):
        for name in ('core:privacy', 'core:terms'):
            with self.subTest(page=name):
                response = self.client.head(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.content, b'')

    def test_close_link_rejects_external_targets_and_policy_loops(self):
        for target in ('https://example.org/', '//example.org/', '/privacy/', '/terms/?anything=1'):
            with self.subTest(target=target):
                response = self.client.get(reverse('core:privacy'), {'next': target})
                self.assertEqual(response.context['close_url'], reverse('home'))

    def test_close_link_accepts_a_relative_application_path(self):
        response = self.client.get(reverse('core:privacy'), {'next': '/landing/'})
        self.assertEqual(response.context['close_url'], '/landing/')

    def test_policy_endpoints_reject_mutation(self):
        for name in ('core:privacy', 'core:terms'):
            with self.subTest(page=name):
                self.assertEqual(self.client.post(reverse(name)).status_code, 405)
