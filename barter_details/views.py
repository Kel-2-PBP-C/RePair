from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.db import transaction

from accounts.utils import profile_initials
from profile_post.models import BarterOffer
from profile_post.views import _get_user_contact
from .forms import BidForm
from .models import Barter

def barter_detail(request, pk):
    barter = get_object_or_404(Barter, pk=pk)
    other_items = Barter.objects.filter(owner=barter.owner).exclude(pk=pk)[:6]
    return render(request, 'barter_details/details.html', {
        'barter': barter,
        'profile_initials': profile_initials(barter.owner),
        'preferred_contact': _get_user_contact(barter.owner),
        'other_items': other_items,
        'bid_form': BidForm(auto_id='%'),
    })
        
@require_POST  
def submit_bid_ajax(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse({'message': 'Kamu harus login sebelum mengajukan penawaran!'}, status=401)
    
    target = get_object_or_404(Barter, pk=pk)
    
    if target.owner == request.user:
        return JsonResponse({'message': 'Kamu tidak bisa mengajukan penawaran untuk barang sendiri!'}, status=403)
    if target.status != Barter.StatusChoices.AVAILABLE:
        return JsonResponse(
            {'message': 'Penawaran hanya dapat diajukan untuk barang yang tersedia.'},
            status=400,
        )
    
    form = BidForm(request.POST)
    if request.method == "POST":
        if form.is_valid():
            with transaction.atomic():
                BarterOffer.objects.create(
                    post=target,
                    offerer=request.user,
                    offered_item_title=form.cleaned_data['replacement_item'],
                    offered_item_description=form.cleaned_data['replacement_description'],
                    offered_item_thumbnail=form.cleaned_data['replacement_thumbnail'],
                    offered_item_location=form.cleaned_data['replacement_location'],
                    offered_item_location_code=form.cleaned_data['replacement_location_code'],
                    offered_item_category=form.cleaned_data['replacement_category'],
                    offered_item_condition=form.cleaned_data['condition'],
                    offerer_contact=_get_user_contact(request.user),
                )
                if not target.is_profile_post:
                    target.is_profile_post = True
                    target.save(update_fields=['is_profile_post', 'updated_at'])
            return JsonResponse({'message': 'Penawaran berhasil diajukan!'}, status=201)
        
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
