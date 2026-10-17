from django.contrib import admin
from .models import Barter


@admin.register(Barter)
class BarterAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'condition', 'item_location', 'created_at')
    readonly_fields = ('id',)
