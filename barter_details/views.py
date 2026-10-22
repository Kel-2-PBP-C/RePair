from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse

from .forms import BidForm
from .models import Barter

def barter_detail(request, pk):
    barter = get_object_or_404(Barter, pk=pk)
    other_items = Barter.objects.filter(owner=barter.owner).exclude(pk=pk)[:6]
    return render(request, 'barter_details/details.html', {
        'barter': barter,
        'other_items': other_items,
        'bid_form': BidForm(auto_id='%'),
    })
        
@require_POST  
def submit_bid_ajax(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse({'message': 'Kamu harus login sebelum membuat Bid!'}, status=401)
    
    target = get_object_or_404(Barter, pk=pk)
    
    if target.owner == request.user:
        return JsonResponse({'message': 'Kamu tidak bisa membuat Bid untuk barang sendiri!'}, status=403)
    
    form=BidForm(request.POST)
    if request.method == "POST":
        if form.is_valid():
            bid = form.save(commit=False)
            bid.target = target
            bid.bidder = request.user
            bid.save()
            return JsonResponse({'message': 'Bid berhasil diajukan!'}, status=201)
        
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
