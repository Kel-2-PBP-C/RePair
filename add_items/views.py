from django.shortcuts import render, get_object_or_404

# Create your views here.
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_POST
from .forms import BarterForm
from barter_details.models import Barter

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
        
@login_required
def edit_barter(request, pk):
    barter = get_object_or_404(Barter, pk=pk, owner=request.user)
    return render(request, 'add_items/add_items.html', {
        'form': BarterForm(instance=barter),
        'barter': barter,
        'is_edit': True,
        })

@require_POST
def edit_barter_ajax(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse({'message':'Kamu harus login terlebih dahulu'}, status=401)
    
    barter = get_object_or_404(Barter, pk=pk, owner=request.user)
    form = BarterForm(request.POST, instance=barter)
    if form.is_valid():
        form.save()
        return JsonResponse({
            'message': 'Barang berhasil diperbarui',
            'redirect_url': reverse('barter_details:barter_detail', args=[barter.pk]),
        }, status=200)
        
    return JsonResponse({'errors': form.errors.get_json_data()}, status=400)

@require_POST
def delete_barter_ajax(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse({'message':'Kamu harus login terlebih dahulu'}, status=401)
    
    barter= get_object_or_404(Barter, pk=pk, owner=request.user)
    barter.delete()
    return JsonResponse({
        'message': 'Barang berhasil dihapus',
        'redirect_url': reverse('add_items:create'), #ini nanti diganti ke landing page aja
    }, status=200)