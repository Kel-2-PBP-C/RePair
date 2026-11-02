"""Offline, transactional checks for importing the public product dataset."""

from copy import deepcopy
from io import StringIO
from unittest.mock import Mock, patch
from uuid import NAMESPACE_URL, uuid5

import requests
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError
from django.test import TestCase

from .models import Barter


API_URL = "https://dummyjson.com/products"
OWNER_USERNAME = "dataset_dummyjson"
SOURCE_CATEGORY_MAP = {
    "smartphones": "elektronik",
    "laptops": "elektronik",
    "tablets": "elektronik",
    "mobile-accessories": "elektronik",
    "furniture": "perabot",
    "home-decoration": "perabot",
    "kitchen-accessories": "perabot",
    "mens-shirts": "pakaian",
    "mens-shoes": "pakaian",
    "mens-watches": "pakaian",
    "womens-dresses": "pakaian",
    "womens-shoes": "pakaian",
    "womens-bags": "pakaian",
    "womens-watches": "pakaian",
    "tops": "pakaian",
    "sports-accessories": "hobi",
}


def source_products(count=50):
    categories = tuple(SOURCE_CATEGORY_MAP)
    return [
        {
            "id": index,
            "title": f"Produk contoh {index}",
            "description": f"Deskripsi produk contoh nomor {index} dari dataset publik.",
            "category": categories[(index - 1) % len(categories)],
            "thumbnail": f"https://cdn.dummyjson.com/product-images/{index}.webp",
        }
        for index in range(1, count + 1)
    ]


def product_uuid(source_id):
    return uuid5(NAMESPACE_URL, f"https://dummyjson.com/products/{source_id}")


class DummyJSONImportTests(TestCase):
    def setUp(self):
        self.products = source_products()
        self.response = Mock(status_code=200)
        self.response.json.return_value = {"products": self.products, "total": len(self.products)}
        self.response.raise_for_status.return_value = None
        self.http = self.enterContext(patch(
            "barter_details.management.commands.import_dummyjson.requests.get",
            return_value=self.response,
        ))

    def run_import(self):
        output = StringIO()
        call_command("import_dummyjson", stdout=output, stderr=StringIO())
        return output.getvalue()

    def assert_no_imported_data(self):
        self.assertFalse(Barter.objects.exists())
        self.assertFalse(get_user_model().objects.filter(username=OWNER_USERNAME).exists())

    def test_imports_fifty_valid_products_with_one_request_and_safe_owner(self):
        self.run_import()
        self.http.assert_called_once_with(
            API_URL,
            params={"limit": 0, "select": "id,title,description,category,thumbnail"},
            timeout=(5, 30),
            allow_redirects=False,
        )
        owner = get_user_model().objects.get(username=OWNER_USERNAME)
        self.assertFalse(owner.is_active)
        self.assertFalse(owner.is_staff)
        self.assertFalse(owner.is_superuser)
        self.assertFalse(owner.has_usable_password())
        self.assertEqual(Barter.objects.count(), 50)
        for product in self.products:
            with self.subTest(source_id=product["id"], source_category=product["category"]):
                item = Barter.objects.get(pk=product_uuid(product["id"]))
                self.assertEqual(item.owner, owner)
                self.assertEqual(item.title, product["title"])
                self.assertEqual(item.description, product["description"])
                self.assertEqual(item.thumbnail, product["thumbnail"])
                self.assertEqual(item.category, SOURCE_CATEGORY_MAP[product["category"]])
                self.assertEqual(item.item_year, 2024)
                self.assertEqual(item.condition, Barter.ConditionChoices.GOOD)
                self.assertEqual(item.condition_percentage, 80)
                self.assertEqual(item.status, Barter.StatusChoices.AVAILABLE)
                self.assertEqual(item.item_location, "Depok (data contoh)")
                self.assertEqual(item.item_replacement, "")
                item.full_clean()

    def test_rerun_updates_existing_rows_without_duplicate_products_or_accounts(self):
        self.run_import()
        initial_owner_id = get_user_model().objects.get(username=OWNER_USERNAME).pk
        initial_item = Barter.objects.get(pk=product_uuid(1))
        original_created_at = initial_item.created_at
        self.products[0].update(
            title="Nama produk terbaru", description="Deskripsi terbaru yang masih valid.",
            thumbnail="https://example.org/updated.webp", category="sports-accessories",
        )
        self.run_import()
        initial_item.refresh_from_db()
        self.assertEqual(Barter.objects.count(), 50)
        self.assertEqual(get_user_model().objects.count(), 1)
        self.assertEqual(initial_item.owner_id, initial_owner_id)
        self.assertEqual(initial_item.title, "Nama produk terbaru")
        self.assertEqual(initial_item.description, "Deskripsi terbaru yang masih valid.")
        self.assertEqual(initial_item.thumbnail, "https://example.org/updated.webp")
        self.assertEqual(initial_item.category, "hobi")
        self.assertEqual(initial_item.created_at, original_created_at)

    def test_selection_and_uuids_are_stable_when_provider_changes_record_order(self):
        self.response.json.return_value = {"products": source_products(80)}
        self.run_import()
        initial_ids = set(Barter.objects.values_list("pk", flat=True))
        self.assertEqual(len(initial_ids), 50)
        self.response.json.return_value["products"].reverse()
        self.run_import()
        self.assertEqual(set(Barter.objects.values_list("pk", flat=True)), initial_ids)
        self.assertEqual(Barter.objects.count(), 50)

    def test_unsupported_categories_are_not_imported(self):
        irrelevant = [
            {**self.products[0], "id": 1001, "category": "groceries"},
            {**self.products[0], "id": 1002, "category": "beauty"},
            {**self.products[0], "id": 1003, "category": "fragrances"},
        ]
        self.response.json.return_value = {"products": irrelevant + self.products}
        self.run_import()
        self.assertEqual(Barter.objects.count(), 50)
        for product in irrelevant:
            self.assertFalse(Barter.objects.filter(pk=product_uuid(product["id"])).exists())

    def test_existing_regular_items_are_preserved(self):
        owner = get_user_model().objects.create_user(username="ordinary-owner", password="ARealPassword!123")
        item = Barter.objects.create(
            owner=owner, title="Barang asli", description="Barang milik pengguna asli.",
            thumbnail="https://example.org/original.jpg", item_year=2020,
            condition="GOOD", condition_percentage=90, item_location="Bogor", category="buku",
        )
        self.run_import()
        item.refresh_from_db()
        self.assertEqual(Barter.objects.count(), 51)
        self.assertEqual(item.owner, owner)
        self.assertEqual(item.title, "Barang asli")
        self.assertEqual(item.category, "buku")

    def test_network_failures_leave_no_partial_import(self):
        for error in (requests.Timeout("provider timeout"), requests.ConnectionError("provider unreachable")):
            with self.subTest(error=type(error).__name__):
                self.http.side_effect = error
                with self.assertRaises(CommandError):
                    self.run_import()
                self.assert_no_imported_data()

    def test_http_errors_and_redirects_are_rejected_without_writes(self):
        for status in (301, 302, 400, 429, 500, 503):
            with self.subTest(status=status):
                self.response.status_code = status
                self.response.raise_for_status.side_effect = (
                    requests.HTTPError(f"HTTP {status}") if status >= 400 else None
                )
                with self.assertRaises(CommandError):
                    self.run_import()
                self.assert_no_imported_data()

    def test_invalid_json_is_reported_without_writes(self):
        self.response.json.side_effect = ValueError("invalid JSON document")
        with self.assertRaises(CommandError):
            self.run_import()
        self.assert_no_imported_data()

    def test_malformed_payloads_are_rejected_without_writes(self):
        for payload in (None, [], "invalid", {}, {"products": None}, {"products": {}}, {"products": "bad"}):
            with self.subTest(payload=payload):
                self.response.json.return_value = payload
                with self.assertRaises(CommandError):
                    self.run_import()
                self.assert_no_imported_data()

    def test_fewer_than_fifty_relevant_records_is_rejected_without_writes(self):
        for products in ([], self.products[:49], [{**p, "category": "groceries"} for p in self.products]):
            with self.subTest(count=len(products)):
                self.response.json.return_value = {"products": products}
                with self.assertRaises(CommandError):
                    self.run_import()
                self.assert_no_imported_data()

    def test_duplicate_source_ids_are_rejected_without_writes(self):
        self.response.json.return_value = {"products": self.products + [deepcopy(self.products[0])]}
        with self.assertRaises(CommandError):
            self.run_import()
        self.assert_no_imported_data()

    def test_malformed_relevant_record_is_not_silently_truncated_or_coerced(self):
        bad_fields = (
            ("id", None), ("id", True), ("id", 0), ("id", -1), ("id", "1"), ("id", 1.5),
            ("title", None), ("title", 123), ("title", ""), ("title", "   "), ("title", "a" * 256),
            ("description", None), ("description", []), ("description", "   "),
            ("thumbnail", None), ("thumbnail", 123), ("thumbnail", "not-a-url"),
            ("thumbnail", "https://example.org/" + "x" * 500),
            ("category", None), ("category", []),
        )
        for field, value in bad_fields:
            with self.subTest(field=field, value=value):
                products = deepcopy(self.products)
                products[-1][field] = value
                self.response.json.return_value = {"products": products}
                with self.assertRaises(CommandError):
                    self.run_import()
                self.assert_no_imported_data()

    def test_missing_required_source_field_is_rejected_without_writes(self):
        for field in ("id", "title", "description", "thumbnail", "category"):
            with self.subTest(field=field):
                products = deepcopy(self.products)
                del products[-1][field]
                self.response.json.return_value = {"products": products}
                with self.assertRaises(CommandError):
                    self.run_import()
                self.assert_no_imported_data()

    def test_non_object_source_record_is_rejected_without_writes(self):
        for malformed in (None, "product", 123, ["product"]):
            with self.subTest(record=malformed):
                self.response.json.return_value = {"products": [*self.products, malformed]}
                with self.assertRaises(CommandError):
                    self.run_import()
                self.assert_no_imported_data()

    def test_existing_username_with_user_privileges_or_password_cannot_be_taken_over(self):
        for unsafe_field in ("is_active", "is_staff", "is_superuser", "password"):
            with self.subTest(unsafe_field=unsafe_field):
                owner = get_user_model().objects.create_user(
                    username=OWNER_USERNAME, password=None, is_active=False,
                )
                if unsafe_field == "password":
                    owner.set_password("ExistingUsersSecret!123")
                else:
                    setattr(owner, unsafe_field, True)
                owner.save()
                original_password = owner.password
                with self.assertRaises(CommandError):
                    self.run_import()
                owner.refresh_from_db()
                self.assertEqual(owner.password, original_password)
                if unsafe_field != "password":
                    self.assertTrue(getattr(owner, unsafe_field))
                self.assertFalse(Barter.objects.exists())
                owner.delete()

    def test_uuid_collision_with_another_owner_aborts_entire_import(self):
        owner = get_user_model().objects.create_user(username="collision-owner")
        collision = Barter.objects.create(
            pk=product_uuid(50), owner=owner, title="Jangan timpa barang ini",
            description="Barang milik pengguna lain yang harus tetap utuh.",
            thumbnail="https://example.org/original.jpg", item_year=2020,
            condition="GOOD", condition_percentage=90, item_location="Bogor", category="buku",
        )
        with self.assertRaises(CommandError):
            self.run_import()
        self.assertEqual(Barter.objects.count(), 1)
        collision.refresh_from_db()
        self.assertEqual(collision.owner, owner)
        self.assertEqual(collision.title, "Jangan timpa barang ini")
        self.assertEqual(collision.category, "buku")
        self.assertFalse(get_user_model().objects.filter(username=OWNER_USERNAME).exists())

    def test_database_error_rolls_back_previously_written_products_and_owner(self):
        original_save = Barter.save
        saves = []

        def fail_after_some_writes(item, *args, **kwargs):
            saves.append(item.pk)
            if len(saves) == 20:
                raise IntegrityError("simulated storage failure")
            return original_save(item, *args, **kwargs)

        with patch.object(Barter, "save", fail_after_some_writes):
            with self.assertRaises(CommandError):
                self.run_import()
        self.assertEqual(len(saves), 20)
        self.assert_no_imported_data()

    def test_invalid_rerun_preserves_previous_successful_dataset(self):
        self.run_import()
        before = list(Barter.objects.order_by("pk").values())
        self.products[0]["title"] = "This update must roll back"
        self.products[-1]["thumbnail"] = "invalid"
        with self.assertRaises(CommandError):
            self.run_import()
        self.assertEqual(list(Barter.objects.order_by("pk").values()), before)

    def test_category_defaults_and_choices_cover_the_application_categories(self):
        category_field = Barter._meta.get_field("category")
        self.assertEqual(category_field.default, "")
        self.assertTrue(category_field.blank)
        self.assertEqual(
            set(value for value, label in category_field.choices),
            {"elektronik", "buku", "pakaian", "perabot", "hobi"},
        )
