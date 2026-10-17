from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from . import regions


@login_required
@require_GET
@never_cache
def region_search(request):
    query = request.GET.get("q", "")
    if len(query) > regions.MAX_QUERY_LENGTH:
        return JsonResponse(
            {"error": "Kata pencarian maksimal 80 karakter.", "results": []},
            status=400,
        )
    try:
        results = regions.search_regions(query)
    except ValueError:
        return JsonResponse(
            {"error": "Kata pencarian tidak valid.", "results": []},
            status=400,
        )
    except regions.RegionServiceError:
        return JsonResponse(
            {
                "error": "Daftar kota sementara tidak tersedia. Coba lagi sebentar.",
                "results": [],
            },
            status=503,
        )
    return JsonResponse({"results": results})
