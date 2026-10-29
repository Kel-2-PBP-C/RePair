
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from .models import CartItem
from barter_details.models import Barter


@login_required
@require_GET
def keranjang(request):
    cart_items = (
        CartItem.objects
        .filter(user=request.user)
        .select_related("barter")
    )

    # Pencarian barang berdasarkan nama.
    search_query = request.GET.get("q", "").strip()
    if search_query:
        cart_items = cart_items.filter(
            barter__title__icontains=search_query
        )

    # Filter barang berdasarkan lokasi.
    location_query = request.GET.get("location", "").strip()
    if location_query:
        cart_items = cart_items.filter(
            barter__item_location__icontains=location_query
        )

    return render(
        request,
        "keranjang/keranjang.html",
        {
            "cart_items": cart_items,
            "search_query": search_query,
            "location_query": location_query,
        },
    )


@login_required
@require_POST
def tambah_keranjang(request, barter_id):
    barter = get_object_or_404(Barter, pk=barter_id)

    # Pengguna tidak boleh menyimpan barang miliknya sendiri.
    if barter.owner_id == request.user.id:
        messages.warning(
            request,
            "Kamu tidak dapat menyimpan barang milikmu sendiri.",
        )
        return redirect("keranjang")

    try:
        _, created = CartItem.objects.get_or_create(
            user=request.user,
            barter=barter,
        )
    except IntegrityError:
        # Menangani kemungkinan duplikasi akibat permintaan bersamaan.
        created = False

    if created:
        messages.success(
            request,
            "Barang berhasil ditambahkan ke keranjang.",
        )
    else:
        messages.info(
            request,
            "Barang tersebut sudah ada di keranjang.",
        )

    return redirect("keranjang")


@login_required
@require_POST
def hapus_keranjang(request, item_id):
    # Item hanya dapat dihapus oleh pemilik keranjangnya.
    item = get_object_or_404(
        CartItem,
        pk=item_id,
        user=request.user,
    )

    item.delete()

    messages.success(
        request,
        "Barang berhasil dihapus dari keranjang.",
    )
    return redirect("keranjang")
