from django.contrib import admin

from .models import Team, TeamMembership


class TeamMembershipInline(admin.TabularInline):
    model = TeamMembership
    extra = 1
    autocomplete_fields = ["user"]


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]
    inlines = [TeamMembershipInline]


@admin.register(TeamMembership)
class TeamMembershipAdmin(admin.ModelAdmin):
    list_display = ["team", "user", "role"]
    list_filter = ["role", "team"]
    search_fields = ["team__name", "user__username"]
    autocomplete_fields = ["team", "user"]