from django.contrib import admin

from .models import Ticket, TicketReference, TeamTicketPolicy

admin.site.register(Ticket)

@admin.register(TicketReference)
class TicketReferenceAdmin(admin.ModelAdmin):
    list_display = (
        "ticket",
        "kind",
        "provider",
        "external_id",
        "title",
        "created_at",
    )
    list_filter = ("kind", "provider", "created_at")
    search_fields = (
        "ticket__title",
        "external_id",
        "title",
        "url",
    )

@admin.register(TeamTicketPolicy)
class TeamTicketPolicyAdmin(admin.ModelAdmin):
    list_display = (
        "team",
        "require_reference_on_close",
        "updated_at",
    )
    list_filter = ("require_reference_on_close",)
    search_fields = ("team__name",)