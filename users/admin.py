from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import PME, Transporteur, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("email", "username", "role", "status", "is_staff")
    list_filter = ("role", "status")
    fieldsets = UserAdmin.fieldsets + (("CargoLink", {"fields": ("role", "status")}),)


@admin.register(Transporteur)
class TransporteurAdmin(admin.ModelAdmin):
    list_display = ("company_name", "user", "verified", "rating")
    list_filter = ("verified",)
    actions = ["valider"]

    @admin.action(description="Valider les transporteurs sélectionnés")
    def valider(self, request, queryset):
        for t in queryset:
            t.verified = True
            t.save()
            t.user.status = User.Status.ACTIVE
            t.user.save()


admin.site.register(PME)
