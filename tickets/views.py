from django.shortcuts import get_object_or_404, redirect, render

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

def ticket_edit(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)

    if request.method == "POST":
        form = TicketForm(request.POST, instance=ticket)

        if form.is_valid():
            form.save()
            return redirect("ticket-list")
    else:
        form = TicketForm(instance=ticket)

    return render(
        request,
        "tickets/ticket_form.html",
        {"form": form},
    )

def ticket_delete(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)

    if request.method == "POST":
        ticket.delete()
        return redirect("ticket-list")

    return render(
        request,
        "tickets/ticket_confirm_delete.html",
        {"ticket": ticket},
    )