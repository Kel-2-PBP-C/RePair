
from django.urls import path
from . import views

urlpatterns = [
    path("", views.keranjang, name="keranjang"),
    path(
        "tambah/<uuid:barter_id>/",
        views.tambah_keranjang,
        name="tambah_keranjang",
    ),
    path(
        "hapus/<int:item_id>/",
        views.hapus_keranjang,
        name="hapus_keranjang",
    ),
]
