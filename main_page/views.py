from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_GET
from barter_details.models import Barter


# @login_required
@require_GET
def show_main(request):
    search = request.GET.get('search', '')
    kondisi = request.GET.get('kondisi', '')

    items = Barter.objects.all()

    if search:
        items = items.filter(title__icontains=search)

    if kondisi == 'baik':
        items = items.filter(condition__gte=80)
    elif kondisi == 'cukup':
        items = items.filter(condition__gte=50, condition__lt=80)
    elif kondisi == 'kurang':
        items = items.filter(condition__lt=50)

    context = {
        'items': items,
        'search': search,
        'kondisi': kondisi,
    }

    return render(request, 'main_page/main_page.html', context)