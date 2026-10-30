from django.shortcuts import render
from django.views.decorators.http import require_GET
from barter_details.models import Barter


@require_GET
def show_main(request):
    items = Barter.objects.all()

    # Mengambil input pencarian dan filter
    search = request.GET.get('search', '').strip()
    kondisi = request.GET.get('kondisi', '')

    # Mencari barang berdasarkan nama
    if search:
        items = items.filter(title__icontains=search)

    # Filter berdasarkan kategori kondisi barang
    if kondisi in ['NEW', 'GOOD', 'REPAIR']:
        items = items.filter(condition=kondisi)

    context = {
        'items': items,
        'search': search,
        'kondisi': kondisi,
    }

    return render(request, "main_page/main_page.html", context)