from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required

from .forms import TicketForm
from .models import Ticket

@login_required
def ticket_list(request):
    status = request.GET.get("status")

    tickets = Ticket.objects.all()

    if status:
        tickets = tickets.filter(status=status)

    tickets = tickets.order_by("due_date")

    return render(
        request,
        "tickets/ticket_list.html",
        {"tickets": tickets, "status_choices": Ticket.Status.choices, "selected_status": status},
    )

@login_required
def ticket_create(request):
    if request.method == "POST":
        form = TicketForm(request.POST)

        if form.is_valid():
            ticket = form.save(commit=False)

        if request.user.is_authenticated:
            ticket.opened_by = request.user

        ticket.save()
        form.save_m2m()
        return redirect("ticket-list")
    else:
        form = TicketForm()

    return render(
        request,
        "tickets/ticket_form.html",
        {"form": form},
    )

@login_required
def ticket_edit(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    old_status = ticket.status

    if request.method == "POST":
        form = TicketForm(request.POST, instance=ticket)

        if form.is_valid():
            updated_ticket = form.save(commit=False)

            if (
                old_status != Ticket.Status.CLOSED
                and updated_ticket.status == Ticket.Status.CLOSED
                and request.user.is_authenticated
            ):
                updated_ticket.closed_by = request.user

            if (
                old_status == Ticket.Status.CLOSED
                and updated_ticket.status != Ticket.Status.CLOSED
            ):
                updated_ticket.closed_by = None

            updated_ticket.save()
            form.save_m2m()

            return redirect("ticket-list")
    else:
        form = TicketForm(instance=ticket)

    return render(
        request,
        "tickets/ticket_form.html",
        {"form": form},
    )

@login_required
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