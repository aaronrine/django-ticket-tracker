from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required

from .forms import TicketForm
from .models import Ticket
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.core.paginator import Paginator

@login_required
def ticket_list(request):
    status = request.GET.get("status")
    priority = request.GET.get("priority")
    overdue = request.GET.get("overdue")
    assignee = request.GET.get("assignee")
    q = request.GET.get("q")
    sort = request.GET.get("sort", "due_date")

    tickets = Ticket.objects.all()

    if status:
        tickets = tickets.filter(status=status)
    if priority:
        tickets = tickets.filter(priority=priority)
    if overdue == "1":
        tickets = tickets.filter(
            due_date__lt=timezone.localdate()
        ).exclude(
            status=Ticket.Status.CLOSED
        )
    if assignee:
        tickets = tickets.filter(assignees__id=assignee)
    if q:
        tickets = tickets.filter(
            Q(title__icontains=q) | Q(description__icontains=q)
        )

    allowed_sorts = {
        "due_date": "due_date",
        "priority": "priority",
        "created_at": "-created_at",
        "updated_at": "-updated_at",
        "title": "title",
    }

    tickets = tickets.order_by(allowed_sorts.get(sort, "due_date"))
    paginator = Paginator(tickets, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    query_params = request.GET.copy()

    if "page" in query_params:
        del query_params["page"]

    User = get_user_model()
    return render(
        request,
        "tickets/ticket_list.html",
        {
            "tickets": page_obj,
            "page_obj": page_obj,
            "status_choices": Ticket.Status.choices,
            "selected_status": status,
            "priority_choices": Ticket.Priority.choices,
            "selected_priority": priority,
            "selected_overdue": overdue,
            "assignees": User.objects.all().order_by("username"),
            "selected_assignees": assignee,
            "search_query": q,
            "selected_sort": sort,
            "query_params": query_params.urlencode(),
        },
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
        {
            "form": form,
            "page_title": "New Ticket",
            "button_text": "Create Ticket",
        },
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
        {
            "form": form,
            "page_title": "Edit Ticket",
            "button_text": "Save Changes",
        },
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