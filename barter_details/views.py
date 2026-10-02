from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, get_object_or_404
from .models import Barter

def barter_detail(request, pk):
    barter = get_object_or_404(Barter, pk=pk)
    other_items = Barter.objects.filter(owner=barter.owner).exclude(pk=pk)[:6]
    return render(request, 'barter_details/details.html', {
        'barter': barter,
        'other_items': other_items,
    })