# Create your tests here.
from datetime import date

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from barter_details.models import Barter
from add_items.forms import BarterForm

TEST_MIDDLEWARE = [
    m for m in settings.MIDDLEWARE
    if 'DevAutoLoginMiddleware' not in m
    and 'GoogleProfileCompletionMiddleware' not in m
]

User = get_user_model()

def valid_data(**overrides):
    data = {
        'title': 'Jakun UI',
        'description': 'Jaket Kuning',
        'thumbnail': 'https://img.lazcdn.com/g/ff/kf/S1d679a22be3b4a65bc6d6565a9b3f030j.jpg_720x720q80.jpg',
        'item_year': '2025',
        'condition': '78',
        'item_location': 'Depok',
        'item_replacement': 'Jamal ITB',
    }
    data.update(overrides)
    return data

def make_barter(owner, **overrides):
    data = valid_data(**overrides)
    return Barter.objects.create(owner=owner, **data)
                
@override_settings(MIDDLEWARE=TEST_MIDDLEWARE, LOGIN_URL='/login/')
class BaseTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username='owner', password='Repair')
        cls.other = User.objects.create_user(username='other', password='Repair')
        
    def login(self, user=None):
        user = user or self.owner
        self.client.force_login(user)
        
class BarterFormTests(TestCase):
    def test_valid_form(self):
        self.assertTrue(BarterForm(data=valid_data()).is_valid())
 
    def test_item_replacement_is_optional(self):
        form = BarterForm(data=valid_data(item_replacement=''))
        self.assertTrue(form.is_valid(), form.errors)
 
    def test_year_below_1900_invalid(self):
        form = BarterForm(data=valid_data(item_year=1899))
        self.assertFalse(form.is_valid())
        self.assertIn('item_year', form.errors)
 
    def test_year_in_future_invalid(self):
        form = BarterForm(data=valid_data(item_year=date.today().year + 1))
        self.assertFalse(form.is_valid())
        self.assertIn('item_year', form.errors)
 
    def test_year_boundaries_valid(self):
        for year in (1900, date.today().year):
            with self.subTest(year=year):
                self.assertTrue(BarterForm(data=valid_data(item_year=year)).is_valid())

    def test_required_fields(self):
        form = BarterForm(data={})
        self.assertFalse(form.is_valid())
        for field in ('title', 'description', 'thumbnail', 'item_year', 'condition', 'item_location'):
            with self.subTest(field=field):
                self.assertIn(field, form.errors)
        
class CreateBarterViewTests(BaseTestCase):
    def test_create_page_requires_login(self):
        response = self.client.get(reverse('add_items:create'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/login/'))
        
    def test_create_page_renders_for_logged_in_user(self):
        self.login()
        response = self.client.get(reverse('add_items:create'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'add_items/add_items.html')
        
class CreateBarterAjaxViewTests(BaseTestCase):
    url_name = 'add_items:create_ajax'
    
    def test_require_post(self):
        self.login()
        response = self.client.get(reverse(self.url_name))
        self.assertEqual(response.status_code, 405)
        
    def test_anonymous_gets_401(self):
        response = self.client.post(reverse(self.url_name), valid_data())
        self.assertEqual(response.status_code, 401)
        self.assertEqual(Barter.objects.count(), 0)
        
    def test_valid_post_creates_barter(self):
        self.login()
        response = self.client.post(reverse(self.url_name), valid_data())
        self.assertEqual(response.status_code, 201)
 
        barter = Barter.objects.get()
        self.assertEqual(barter.owner, self.owner)
        self.assertEqual(barter.title, 'Jakun UI')
 
        body = response.json()
        self.assertEqual(body['message'], 'Barang berhasil ditambahkan!')
        self.assertEqual(
            body['redirect_url'],
            reverse('barter_details:barter_detail', args=[barter.pk]),
        )
 
    def test_owner_cannot_be_spoofed_from_post_data(self):
        self.login()
        self.client.post(reverse(self.url_name), valid_data(owner=self.other.pk))
        self.assertEqual(Barter.objects.get().owner, self.owner)
 
    def test_invalid_post_returns_400_with_errors(self):
        self.login()
        response = self.client.post(reverse(self.url_name), valid_data(title=''))
        self.assertEqual(response.status_code, 400)
        self.assertIn('title', response.json()['errors'])
        self.assertEqual(Barter.objects.count(), 0)
 
    def test_invalid_year_returns_400(self):
        self.login()
        response = self.client.post(reverse(self.url_name), valid_data(item_year=1800))
        self.assertEqual(response.status_code, 400)
        errors = response.json()['errors']
        self.assertIn('item_year', errors)
        self.assertEqual(errors['item_year'][0]['message'], 'Tahun tidak valid')
    
class EditBarterViewTest(BaseTestCase):
    def setUp(self):
        self.barter = make_barter(self.owner)
        self.url = reverse('add_items:edit', args=[self.barter.pk])
 
    def test_requires_login(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)
 
    def test_owner_sees_prefilled_form(self):
        self.login()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'add_items/add_items.html')
        self.assertTrue(response.context['is_edit'])
        self.assertEqual(response.context['barter'], self.barter)
        self.assertEqual(response.context['form'].instance, self.barter)
 
    def test_non_owner_gets_404(self):
        self.login(self.other)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        
class EditBarterAjaxTests(BaseTestCase):
    def setUp(self):
        self.barter = make_barter(self.owner)
        self.url = reverse('add_items:edit_ajax', args=[self.barter.pk])
 
    def test_requires_post(self):
        self.login()
        self.assertEqual(self.client.get(self.url).status_code, 405)
 
    def test_anonymous_gets_401(self):
        response = self.client.post(self.url, valid_data(title='Hacked'))
        self.assertEqual(response.status_code, 401)
        self.barter.refresh_from_db()
        self.assertEqual(self.barter.title, 'Jakun UI')
 
    def test_owner_can_update(self):
        self.login()
        response = self.client.post(self.url, valid_data(title='Jakang Arung', condition=90))
        self.assertEqual(response.status_code, 200)
 
        self.barter.refresh_from_db()
        self.assertEqual(self.barter.title, 'Jakang Arung')
        self.assertEqual(self.barter.condition, 90)
        self.assertEqual(
            response.json()['redirect_url'],
            reverse('barter_details:barter_detail', args=[self.barter.pk]),
        )
 
    def test_non_owner_gets_404_and_nothing_changes(self):
        self.login(self.other)
        response = self.client.post(self.url, valid_data(title='Hacked'))
        self.assertEqual(response.status_code, 404)
        self.barter.refresh_from_db()
        self.assertEqual(self.barter.title, 'Jakun UI')
 
    def test_invalid_data_returns_400(self):
        self.login()
        response = self.client.post(self.url, valid_data(item_year=1800))
        self.assertEqual(response.status_code, 400)
        self.assertIn('item_year', response.json()['errors'])
        self.barter.refresh_from_db()
        self.assertEqual(self.barter.item_year, 2025)

class DeleteBarterAjaxTests(BaseTestCase):
    def setUp(self):
        self.barter = make_barter(self.owner)
        self.url = reverse('barter_details:delete_ajax', args=[self.barter.pk])
 
    def test_requires_post(self):
        self.login()
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertTrue(Barter.objects.filter(pk=self.barter.pk).exists())
 
    def test_anonymous_gets_401(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 401)
        self.assertTrue(Barter.objects.filter(pk=self.barter.pk).exists())
 
    def test_owner_can_delete(self):
        self.login()
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Barter.objects.filter(pk=self.barter.pk).exists())
        self.assertEqual(response.json()['redirect_url'], reverse('add_items:create'))
 
    def test_non_owner_gets_404_and_barter_remains(self):
        self.login(self.other)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Barter.objects.filter(pk=self.barter.pk).exists())