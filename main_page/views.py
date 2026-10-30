from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_GET
from barter_details.models import Barter


# @login_required
@require_GET
def show_main(request):
    items = Barter.objects.filter(status=Barter.StatusChoices.AVAILABLE).exclude(owner=request.user)

    # Mengambil input pencarian dan filter dari user
    search = request.GET.get('search', '').strip()
    kondisi = request.GET.get('kondisi', '')

    # Mencari barang berdasarkan nama
    if search:
        items = items.filter(title__icontains=search)

    if kondisi in Barter.ConditionChoices.values:
        items = items.filter(condition=kondisi)

    context = {
        'items': items,
        'search': search,
        'kondisi': kondisi,
    }

    return render(request, "main_page/main_page.html", context)