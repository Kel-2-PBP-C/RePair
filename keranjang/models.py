
from django.conf import settings
from django.db import models


class CartItem(models.Model):
    # Pengguna yang menyimpan barang ke keranjang.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart_items",
    )

    # Referensi ke barang asli, bukan salinan datanya.
    barter = models.ForeignKey(
        "barter_details.Barter",
        on_delete=models.CASCADE,
        related_name="cart_items",
    )

    # Waktu barang ditambahkan ke keranjang.
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "barter"],
                name="unique_user_cart_barter",
            )
        ]

    def __str__(self):
        return f"{self.user} - {self.barter.title}"
