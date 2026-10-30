"""Import a reproducible sample of public DummyJSON products into Barter."""

from collections import Counter
from itertools import islice, zip_longest
from uuid import NAMESPACE_URL, uuid5

import requests
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, transaction

from barter_details.models import Barter


API_URL = "https://dummyjson.com/products"
OWNER_USERNAME = "dataset_dummyjson"
IMPORT_COUNT = 50
CATEGORY_MAP = {
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


def fetch_products():
    # No pagination, retries, image downloads, or per-product requests.
    try:
        response = requests.get(
            API_URL,
            params={"limit": 0, "select": "id,title,description,category,thumbnail"},
            timeout=(5, 30),
            allow_redirects=False,
        )
        if response.status_code != 200:
            raise CommandError("DummyJSON tidak mengembalikan HTTP 200; impor dibatalkan.")
        payload = response.json()
    except (requests.RequestException, ValueError):
        raise CommandError("Gagal mengambil JSON dari DummyJSON; tidak ada data yang disimpan.") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("products"), list):
        raise CommandError("Respons DummyJSON harus berisi daftar products.")
    return payload["products"]


def select_products(products):
    groups = {category: [] for category in ("elektronik", "perabot", "pakaian", "hobi")}
    seen_ids = set()
    for product in products:
        if not isinstance(product, dict) or not isinstance(product.get("category"), str):
            raise CommandError("Struktur produk DummyJSON tidak valid.")
        category = CATEGORY_MAP.get(product["category"])
        if category is None:
            continue
        source_id = product.get("id")
        if type(source_id) is not int or source_id <= 0:
            raise CommandError("ID produk DummyJSON harus berupa bilangan bulat positif.")
        if source_id in seen_ids:
            raise CommandError("Respons DummyJSON memuat ID produk duplikat.")
        seen_ids.add(source_id)
        fields = {}
        for field in ("title", "description", "thumbnail"):
            value = product.get(field)
            if not isinstance(value, str) or not value.strip():
                raise CommandError(f"Produk DummyJSON {source_id}: field {field} tidak valid.")
            fields[field] = value.strip()
        fields.update(
            category=category,
            # These are explicit demo defaults, not facts supplied by DummyJSON.
            item_year=2024,
            condition=Barter.ConditionChoices.GOOD,
            condition_percentage=80,
            status=Barter.StatusChoices.AVAILABLE,
            item_location="Depok (data contoh)",
            item_replacement="",
        )
        identifier = uuid5(NAMESPACE_URL, f"{API_URL}/{source_id}")
        try:
            Barter(pk=identifier, **fields).full_clean(
                exclude=["owner"], validate_unique=False, validate_constraints=False,
            )
        except ValidationError:
            raise CommandError(f"Produk DummyJSON {source_id} tidak sesuai validasi model Barter.") from None
        groups[category].append((source_id, identifier, fields))
    if len(seen_ids) < IMPORT_COUNT:
        raise CommandError(f"Minimal {IMPORT_COUNT} produk relevan diperlukan; ditemukan {len(seen_ids)}.")
    for group in groups.values():
        group.sort(key=lambda product: product[0])
    # Interleave categories so high source IDs (e.g. sports) still get represented.
    selected = list(islice(
        (product for row in zip_longest(*groups.values()) for product in row if product is not None),
        IMPORT_COUNT,
    ))
    return selected, len(seen_ids)


class Command(BaseCommand):
    help = "Impor 50 produk DummyJSON ke Barter; aman dijalankan ulang tanpa duplikasi UUID."
    requires_migrations_checks = True

    def handle(self, *args, **options):
        products = fetch_products()
        selected, relevant_count = select_products(products)
        created_count = 0
        try:
            with transaction.atomic():
                owner, _ = get_user_model().objects.select_for_update().get_or_create(
                    username=OWNER_USERNAME,
                    defaults={
                        "is_active": False, "is_staff": False, "is_superuser": False,
                        "password": make_password(None), "first_name": "Dataset DummyJSON",
                    },
                )
                if owner.is_active or owner.is_staff or owner.is_superuser or owner.has_usable_password():
                    raise CommandError(
                        "Username dataset_dummyjson sudah dipakai akun biasa; impor dibatalkan."
                    )
                for _, identifier, fields in selected:
                    existing = Barter.objects.select_for_update().filter(pk=identifier).first()
                    if existing is not None and existing.owner_id != owner.pk:
                        raise CommandError("UUID dataset dimiliki pengguna lain; impor dibatalkan.")
                    _, created = Barter.objects.update_or_create(
                        pk=identifier, owner=owner, defaults=fields,
                    )
                    created_count += int(created)
        except DatabaseError:
            raise CommandError("Gagal menyimpan dataset; seluruh perubahan impor dibatalkan.") from None
        counts = Counter(fields["category"] for _, _, fields in selected)
        self.stdout.write(self.style.SUCCESS(
            f"Impor selesai: {IMPORT_COUNT} produk ({created_count} baru, "
            f"{IMPORT_COUNT - created_count} diperbarui), owner={OWNER_USERNAME}."
        ))
        self.stdout.write(f"Sumber: {API_URL}; diterima={len(products)}, relevan={relevant_count}.")
        self.stdout.write(", ".join(f"{category}={count}" for category, count in sorted(counts.items())))
