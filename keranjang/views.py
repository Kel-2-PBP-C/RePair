
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages

from .models import CartItem
from barter_details.models import Barter


@login_required
def keranjang(request):
    cart_items = (
        CartItem.objects
        .filter(user=request.user)
        .select_related("barter")
    )

    return render(
        request,
        "keranjang/keranjang.html",
        {"cart_items": cart_items},
    )


@login_required
def tambah_keranjang(request, barter_id):
    if request.method != "POST":
        return redirect("keranjang")

    barter = get_object_or_404(Barter, pk=barter_id)

    if barter.owner_id == request.user.id:
        messages.warning(
            request,
            "Kamu tidak perlu menyimpan barang milikmu sendiri.",
        )
        return redirect("keranjang")

    _, created = CartItem.objects.get_or_create(
        user=request.user,
        barter=barter,
    )

    if created:
        messages.success(request, "Barang berhasil ditambahkan ke keranjang.")
    else:
        messages.info(request, "Barang sudah ada di keranjang.")

    return redirect("keranjang")


@login_required
def hapus_keranjang(request, item_id):
    if request.method != "POST":
        return redirect("keranjang")

    item = get_object_or_404(
        CartItem,
        pk=item_id,
        user=request.user,
    )
    item.delete()

    messages.success(request, "Barang berhasil dihapus dari keranjang.")
    return redirect("keranjang")
