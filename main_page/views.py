from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_GET
from barter_details.models import Barter


# @login_required
@require_GET
def show_main(request):
    items = Barter.objects.all()

    # Mengambil input pencarian dan filter dari user
    search = request.GET.get('search', '').strip()
    kondisi = request.GET.get('kondisi', '')

    # Mencari barang berdasarkan nama
    if search:
        items = items.filter(title__icontains=search)

    # Filter berdasarkan persentase kondisi barang
    if kondisi == 'baik':
        items = items.filter(condition__gte=80, condition__lte=100)
    elif kondisi == 'cukup':
        items = items.filter(condition__gte=50, condition__lt=80)
    elif kondisi == 'kurang':
        items = items.filter(condition__lt=50)

    context = {
        'items': items,
        'search': search,
        'kondisi': kondisi,
    }

    return render(request, "main_page/main_page.html", context)