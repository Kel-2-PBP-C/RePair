
from django.contrib import admin

from .models import CartItem


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "barter",
        "is_favorite",
        "created_at",
    )

    list_filter = (
        "is_favorite",
        "created_at",
    )

    search_fields = (
        "user__username",
        "barter__title",
    )

    list_select_related = (
        "user",
        "barter",
    )

    ordering = (
        "-created_at",
    )
