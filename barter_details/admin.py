from django.contrib import admin
from .models import Barter


@admin.register(Barter)
class BarterAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'category', 'condition', 'item_location', 'created_at')
    list_filter = ('category',)
    readonly_fields = ('id',)
