from django.urls import path

from . import views


urlpatterns = [
    path("", views.ticket_list, name="ticket-list"),
    path("new/", views.ticket_create, name="ticket-create"),
    path("<int:pk>/edit/", views.ticket_edit, name="ticket-edit"),
    path("<int:pk>/delete/", views.ticket_delete, name="ticket-delete"),
    path(
        "<int:pk>/references/new/",
        views.ticket_reference_create,
        name="ticket-reference-create",
    ),
    path("<int:pk>/detail/", views.ticket_detail, name="ticket-detail"),
    path(
        "<int:pk>/subtickets/new/",
        views.ticket_subticket_create,
        name="ticket-subticket-create",
    ),
    path(
        "<int:pk>/status/",
        views.ticket_status_update,
        name="ticket-status-update",
    ),
    
]