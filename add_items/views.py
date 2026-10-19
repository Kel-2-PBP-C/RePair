from django.shortcuts import render

# Create your views here.
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_POST
from .forms import BarterForm

@login_required
def create_barter(request):
    return render(request, 'add_items/add_items.html', {'form': BarterForm()})

@require_POST
def create_barter_ajax(request):
    if not request.user.is_authenticated:
        return JsonResponse({'message': 'Kamu harus Login terlebih dahulu untuk menambah barang!'}, status=401)
    
    form = BarterForm(request.POST)
    if form.is_valid():
        barter = form.save(commit=False)
        barter.owner = request.user
        barter.save()
        return JsonResponse({
            'message': 'Barang berhasil ditambahkan!',
            'redirect_url': reverse('barter_details:barter_detail', args=[barter.pk]),
        }, status=201)
        
    return JsonResponse({'errors': form.errors.get_json_data()}, status = 400)
        