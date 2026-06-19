from django.contrib import admin

from .models import (
    Ticket,
    TicketReference,
    TeamTicketPolicy,
    TicketEvent,
    NotificationChannel,
    NotificationRule,
    NotificationDelivery,
)

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

@admin.register(TicketEvent)
class TicketEventAdmin(admin.ModelAdmin):
    list_display = (
        "ticket",
        "event_type",
        "actor",
        "created_at",
    )
    list_filter = ("event_type", "created_at")
    search_fields = (
        "ticket__title",
        "actor__username",
    )
    readonly_fields = (
        "ticket",
        "actor",
        "event_type",
        "old_values",
        "new_values",
        "created_at",
    )

@admin.register(NotificationChannel)
class NotificationChannelAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "team",
        "provider",
        "is_active",
        "updated_at",
    )
    list_filter = ("provider", "is_active")
    search_fields = ("name", "team__name", "webhook_url")


@admin.register(NotificationRule)
class NotificationRuleAdmin(admin.ModelAdmin):
    list_display = (
        "team",
        "channel",
        "event_type",
        "is_active",
    )
    list_filter = ("event_type", "is_active")
    search_fields = ("team__name", "channel__name")


@admin.register(NotificationDelivery)
class NotificationDeliveryAdmin(admin.ModelAdmin):
    list_display = (
        "event",
        "channel",
        "status",
        "attempts",
        "created_at",
        "sent_at",
    )
    list_filter = ("status", "channel__provider", "created_at")
    search_fields = ("event__ticket__title", "channel__name", "last_error")
    readonly_fields = (
        "event",
        "channel",
        "status",
        "attempts",
        "last_error",
        "created_at",
        "sent_at",
    )