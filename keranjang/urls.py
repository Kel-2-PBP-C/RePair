
from django.urls import path
from . import views

app_name = "keranjang"

urlpatterns = [
    # Halaman utama keranjang.
    path(
        "",
        views.keranjang,
        name="keranjang",
    ),

    # Menambahkan barang ke keranjang.
    path(
        "tambah/<uuid:barter_id>/",
        views.tambah_keranjang,
        name="tambah_keranjang",
    ),

    # Menghapus barang dari keranjang.
    path(
        "hapus/<int:item_id>/",
        views.hapus_keranjang,
        name="hapus_keranjang",
    ),

    # Menandai atau membatalkan favorit barang.
    path(
        "favorit/<int:item_id>/",
        views.toggle_favorit,
        name="toggle_favorit",
    ),
]
