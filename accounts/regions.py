import hashlib
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from django.conf import settings
from django.core.cache import cache


API_BASE_URL = "https://api.bogortech.com/v1/wilayah"
REQUEST_TIMEOUT = (3.05, 8)
DIRECTORY_CACHE_SECONDS = 24 * 60 * 60
SEARCH_CACHE_SECONDS = 5 * 60
MAX_QUERY_LENGTH = 80
MAX_RESULTS = 50
MAX_REGION_LABEL_LENGTH = 150
PROVINCE_CODE_RE = re.compile(r"^[0-9]{2}$")
REGION_CODE_RE = re.compile(r"^[0-9]{2}\.[0-9]{2}$")
_CACHE_PREFIX = "regions:bogortech:v1:"
_INITIAL_CITY_QUERIES = (
    "Jakarta", "Depok", "Bandung", "Surabaya", "Medan", "Yogyakarta",
    "Denpasar", "Balikpapan", "Makassar", "Jayapura",
)


class RegionServiceError(Exception):
    pass


RegionServiceUnavailable = RegionServiceError


def _api_key():
    configured_key = getattr(settings, "BOGORTECH_API_KEY", "")
    key = configured_key.strip() if isinstance(configured_key, str) else ""
    if not key:
        raise RegionServiceUnavailable("Pencarian kota sementara tidak tersedia.")
    return key


def _request_records(path, *, params=None):
    key = _api_key()
    tls_options = {}
    ca_bundle = getattr(settings, "BOGORTECH_CA_BUNDLE", "")
    if isinstance(ca_bundle, str) and ca_bundle.strip():
        tls_options["verify"] = ca_bundle.strip()
    try:
        response = requests.get(
            f"{API_BASE_URL}/{path}",
            headers={"X-API-KEY": key, "Accept": "application/json"},
            params=params,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=False,
            **tls_options,
        )
        if response.status_code != 200:
            raise RegionServiceUnavailable("Pencarian kota sementara tidak tersedia.")
        if len(response.content) > 2 * 1024 * 1024:
            raise RegionServiceUnavailable("Pencarian kota sementara tidak tersedia.")
        payload = response.json()
    except (requests.RequestException, ValueError, TypeError, OSError):
        raise RegionServiceUnavailable("Pencarian kota sementara tidak tersedia.") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise RegionServiceUnavailable("Pencarian kota sementara tidak tersedia.")
    if payload.get("success") is False or len(payload["data"]) > 20000:
        raise RegionServiceUnavailable("Pencarian kota sementara tidak tersedia.")
    return payload["data"]


def _record(record, code_pattern):
    if not isinstance(record, dict):
        return None
    code, name = record.get("code"), record.get("name")
    if not isinstance(code, str) or not code_pattern.fullmatch(code):
        return None
    if not isinstance(name, str):
        return None
    name = " ".join(name.split())
    if not name or len(name) > 120 or any(ord(character) < 32 for character in name):
        return None
    return {"code": code, "name": name}


def _provinces():
    key = f"{_CACHE_PREFIX}provinces"
    provinces = cache.get(key)
    if provinces is not None:
        return provinces
    provinces = {}
    for source in _request_records("provinces"):
        record = _record(source, PROVINCE_CODE_RE)
        if record:
            provinces[record["code"]] = record["name"]
    if not provinces:
        raise RegionServiceUnavailable("Pencarian kota sementara tidak tersedia.")
    cache.set(key, provinces, DIRECTORY_CACHE_SECONDS)
    return provinces


def _canonical_region(record, provinces):
    region = _record(record, REGION_CODE_RE)
    if not region:
        return None
    province_code = region["code"].split(".", 1)[0]
    province_name = provinces.get(province_code)
    if not province_name:
        return None
    label = f"{region['name']}, {province_name}"
    if len(label) > MAX_REGION_LABEL_LENGTH:
        return None
    return {
        **region,
        "province_code": province_code,
        "province_name": province_name,
        "label": label,
    }


def _search_provider(query, provinces):
    digest = hashlib.sha256(query.casefold().encode("utf-8")).hexdigest()
    key = f"{_CACHE_PREFIX}search:{digest}"
    regions = cache.get(key)
    if regions is None:
        by_code = {}
        for source in _request_records("search", params={"q": query}):
            region = _canonical_region(source, provinces)
            if region:
                by_code[region["code"]] = region
        regions = list(by_code.values())
        cache.set(key, regions, SEARCH_CACHE_SECONDS)
    return regions


def search_regions(query="", limit=30):
    """Prefix kota/kabupaten menghindari batas hasil pencarian global yang juga mencakup desa."""
    if not isinstance(query, str):
        raise ValueError("Kata pencarian tidak valid.")
    query = " ".join(query.split())
    if len(query) > MAX_QUERY_LENGTH:
        raise ValueError("Kata pencarian terlalu panjang.")
    _api_key()
    try:
        limit = max(1, min(int(limit), MAX_RESULTS))
    except (TypeError, ValueError):
        limit = 30
    if not query:
        provider_queries = _INITIAL_CITY_QUERIES
    elif query.casefold().startswith(("kota ", "kabupaten ")):
        provider_queries = [query]
    else:
        provider_queries = [query, f"Kota {query}", f"Kabupaten {query}"]
    provinces = _provinces()
    by_code = {}
    with ThreadPoolExecutor(max_workers=min(3, len(provider_queries))) as executor:
        searches = [
            executor.submit(_search_provider, provider_query, provinces)
            for provider_query in provider_queries
        ]
        try:
            for search in as_completed(searches):
                for region in search.result():
                    by_code[region["code"]] = region
        except RegionServiceError:
            for search in searches:
                search.cancel()
            raise
    if query:
        regions = sorted(by_code.values(), key=lambda region: region["label"].casefold())
    else:
        regions = sorted(
            by_code.values(),
            key=lambda region: (
                not region["name"].casefold().startswith("kota "),
                region["label"].casefold(),
            ),
        )
    return regions[:limit]


def lookup_region(code):
    if not isinstance(code, str) or not REGION_CODE_RE.fullmatch(code):
        return None
    _api_key()
    provinces = _provinces()
    province_code = code.split(".", 1)[0]
    if province_code not in provinces:
        return None
    key = f"{_CACHE_PREFIX}regencies:{province_code}"
    regions = cache.get(key)
    if regions is None:
        regions = {}
        for source in _request_records(f"regencies/{province_code}"):
            region = _canonical_region(source, provinces)
            if region and region["province_code"] == province_code:
                regions[region["code"]] = region
        if not regions:
            raise RegionServiceUnavailable("Pencarian kota sementara tidak tersedia.")
        cache.set(key, regions, DIRECTORY_CACHE_SECONDS)
    return regions.get(code)
