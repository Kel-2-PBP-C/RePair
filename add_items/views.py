from django.shortcuts import render, get_object_or_404

# Create your views here.
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_POST
from .forms import BarterForm
from barter_details.models import Barter
from profile_post.forms import PostForm
from profile_post.views import _get_user_default_region

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
        'form': PostForm(instance=barter, mark_as_profile_post=False),
        'barter': barter,
        'is_edit': True,
        })

@require_POST
def edit_barter_ajax(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse({'message':'Kamu harus login terlebih dahulu'}, status=401)
    
    barter = get_object_or_404(Barter, pk=pk, owner=request.user)
    if barter.status != Barter.StatusChoices.AVAILABLE:
        return JsonResponse(
            {'message': 'Barang tidak dapat diedit saat sedang dinegosiasikan atau sudah dibarter.'},
            status=400,
        )

    form = PostForm(
        request.POST,
        instance=barter,
        mark_as_profile_post=False,
    )
    if form.is_valid():
        updated_barter = form.save(commit=False)
        if not updated_barter.location_code and not updated_barter.item_location:
            updated_barter.location_code, updated_barter.item_location = (
                _get_user_default_region(request.user)
            )
        updated_barter.save()
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
        'redirect_url': reverse('add_items:create'), #TODO: ini nanti diganti ke landing page aja
    }, status=200)