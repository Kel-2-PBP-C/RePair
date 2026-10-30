
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from barter_details.models import Barter

from .forms import FavoriteForm
from .models import CartItem


@login_required
@require_GET
def keranjang(request):
    # Mengambil barang milik pengguna yang sedang login.
    cart_items = (
        CartItem.objects
        .filter(user=request.user)
        .select_related("barter")
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
        return redirect("keranjang:keranjang")

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

    return redirect("keranjang:keranjang")


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

    # Jika request mengirim nilai is_favorite,
    # gunakan nilai tersebut melalui FavoriteForm.
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
        # Jika tidak ada nilai yang dikirim,
        # balik status favorit saat ini.
        item.is_favorite = not item.is_favorite

        item.save(
            update_fields=["is_favorite"]
        )

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
        messages.success(
            request,
            message,
        )
    else:
        messages.info(
            request,
            message,
        )

    return redirect("keranjang:keranjang")
