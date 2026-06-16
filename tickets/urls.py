from django.urls import path

from . import views


urlpatterns = [
    path("", views.ticket_list, name="ticket-list"),
    path("new/", views.ticket_create, name="ticket-create"),
    path("<int:pk>/edit/", views.ticket_edit, name="ticket-edit"),
    path("<int:pk>/delete/", views.ticket_delete, name="ticket-delete"),
]