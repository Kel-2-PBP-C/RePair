
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST
from django.db.models import Prefetch

from .models import CartItem
from barter_details.models import Barter
from profile_post.models import BarterOffer, BarterReview


@login_required
@require_GET
def keranjang(request):
    cart_items = (
        CartItem.objects
        .filter(user=request.user)
        .select_related("barter", "barter__owner", "barter__owner__profile")
        .prefetch_related(
            Prefetch(
                "barter__offers",
                queryset=BarterOffer.objects.filter(
                    offerer=request.user,
                    is_selected=True,
                ),
                to_attr="cart_user_selected_offers",
            ),
            Prefetch(
                "barter__reviews",
                queryset=BarterReview.objects.filter(
                    reviewer=request.user,
                    role=BarterReview.RoleChoices.OFFERER_TO_OWNER,
                ),
                to_attr="cart_user_reviews",
            ),
        )
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

    # Barang favorit ditampilkan lebih dahulu.
    cart_items = cart_items.order_by(
        "-is_favorite",
        "-created_at",
    )
    for cart_item in cart_items:
        barter = cart_item.barter
        cart_item.owner_contact = (
            getattr(getattr(barter.owner, "profile", None), "social_contact", "")
            or ""
        ).strip()
        cart_item.user_selected_offer = next(
            iter(barter.cart_user_selected_offers),
            None,
        )
        cart_item.user_barter_review = next(
            iter(barter.cart_user_reviews),
            None,
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
        return redirect("main_page:show_main")

    _, created = CartItem.objects.get_or_create(
        user=request.user,
        barter=barter,
    )

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

    return redirect("main_page:show_main")


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
    return redirect("keranjang:keranjang")


@login_required
@require_POST
def toggle_favorit(request, item_id):
    # User hanya dapat mengubah favorit barang miliknya sendiri.
    item = get_object_or_404(
        CartItem,
        pk=item_id,
        user=request.user,
    )

    # Mengubah status favorit.
    item.is_favorite = not item.is_favorite
    item.save(update_fields=["is_favorite"])

    if item.is_favorite:
        messages.success(
            request,
            "Barang berhasil ditambahkan ke favorit.",
        )
    else:
        messages.info(
            request,
            "Barang dihapus dari favorit.",
        )

    return redirect("keranjang:keranjang")
