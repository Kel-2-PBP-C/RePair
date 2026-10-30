
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from barter_details.models import Barter
from profile_post.models import BarterOffer, BarterReview

from .forms import FavoriteForm
from .models import CartItem


@login_required
@require_GET
def keranjang(request):
    # Mengambil barang milik pengguna yang sedang login.
    cart_items = (
        CartItem.objects
        .filter(user=request.user)
        .select_related(
            "barter",
            "barter__owner",
            "barter__owner__profile",
        )
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

    # Pencarian berdasarkan nama barang.
    search_query = request.GET.get("q", "").strip()

    if search_query:
        cart_items = cart_items.filter(
            barter__title__icontains=search_query
        )

    # Filter berdasarkan lokasi barang.
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

    # Menyiapkan informasi tambahan untuk template.
    for cart_item in cart_items:
        barter = cart_item.barter

        cart_item.owner_contact = (
            getattr(
                getattr(barter.owner, "profile", None),
                "social_contact",
                "",
            ) or ""
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
    # Mengambil barang berdasarkan ID.
    barter = get_object_or_404(
        Barter,
        pk=barter_id,
    )

    # Mencegah pengguna menyimpan barang miliknya sendiri.
    if barter.owner_id == request.user.id:
        messages.warning(
            request,
            "Kamu tidak dapat menyimpan barang milikmu sendiri.",
        )
        return redirect("main_page:show_main")

    # Menambahkan barang jika belum ada di keranjang.
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
    # Memastikan barang benar-benar milik pengguna yang login.
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
    # Memastikan pengguna hanya dapat mengubah favorit miliknya.
    item = get_object_or_404(
        CartItem,
        pk=item_id,
        user=request.user,
    )

    # Jika nilai favorit dikirim melalui form.
    if "is_favorite" in request.POST:
        form = FavoriteForm(
            request.POST,
            instance=item,
        )

        if not form.is_valid():
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse(
                    {
                        "success": False,
                        "errors": form.errors.get_json_data(),
                    },
                    status=400,
                )

            messages.error(
                request,
                "Status favorit gagal diperbarui.",
            )

            return redirect("keranjang:keranjang")

        updated_item = form.save()

    else:
        # Jika tidak ada nilai yang dikirim, balik status favorit.
        item.is_favorite = not item.is_favorite
        item.save(update_fields=["is_favorite"])
        updated_item = item

    # Menyiapkan pesan sesuai status favorit.
    message = (
        "Barang berhasil ditambahkan ke favorit."
        if updated_item.is_favorite
        else "Barang dihapus dari favorit."
    )

    # Mengembalikan JSON untuk permintaan AJAX.
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse(
            {
                "success": True,
                "is_favorite": updated_item.is_favorite,
                "message": message,
            }
        )

    # Menampilkan pesan untuk request biasa.
    if updated_item.is_favorite:
        messages.success(request, message)
    else:
        messages.info(request, message)

    return redirect("keranjang:keranjang")
