from django.shortcuts import redirect, render

from .forms import TicketForm
from .models import Ticket


def ticket_list(request):
    tickets = Ticket.objects.all().order_by("-created_at")

    return render(
        request,
        "tickets/ticket_list.html",
        {"tickets": tickets},
    )


def ticket_create(request):
    if request.method == "POST":
        form = TicketForm(request.POST)

        if form.is_valid():
            form.save()
            return redirect("ticket-list")
    else:
        form = TicketForm()

    return render(
        request,
        "tickets/ticket_form.html",
        {"form": form},
    )