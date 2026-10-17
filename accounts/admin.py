from django.contrib import admin

from .models import GoogleIdentity, Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "domicile", "language", "profile_visibility")
    search_fields = ("user__username", "user__email", "domicile")


@admin.register(GoogleIdentity)
class GoogleIdentityAdmin(admin.ModelAdmin):
    list_display = ('user', 'email', 'created_at')
    search_fields = ('user__username', 'email')
    readonly_fields = ('user', 'subject', 'email', 'created_at')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
