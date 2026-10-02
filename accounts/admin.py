from django.contrib import admin

from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "domicile", "language", "profile_visibility")
    search_fields = ("user__username", "user__email", "domicile")
