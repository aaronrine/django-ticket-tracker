from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from .forms import TicketForm
from .models import Ticket
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.core.paginator import Paginator
from teams.models import Team
from django.http import HttpResponseForbidden
from urllib.parse import urlencode
from django.contrib import messages
import json

from django.core.exceptions import ValidationError
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST

from teams.permissions import can_view_team_ticket, can_delete_team_ticket, can_change_team_ticket_status, can_create_team_ticket, can_create_team_subticket

@login_required
def ticket_list(request):
    status = request.GET.get("status")
    priority = request.GET.get("priority")
    overdue = request.GET.get("overdue")
    assigned_user = request.GET.get("assigned_user")
    assigned_team = request.GET.get("assigned_team")
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
    if assigned_user:
        tickets = tickets.filter(assigned_user__id=assigned_user)
    if assigned_team:
        tickets = tickets.filter(assigned_team__id=assigned_team)
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

    kanban_columns = []

    for status_value, status_label in Ticket.Status.choices:
        kanban_columns.append({
            "value": status_value,
            "label": status_label,
            "tickets": tickets.filter(status=status_value),
        })

    User = get_user_model()
    return render(
        request,
        "tickets/ticket_list.html",
        {
            "tickets": tickets,
            "status_choices": Ticket.Status.choices,
            "selected_status": status,
            "priority_choices": Ticket.Priority.choices,
            "selected_priority": priority,
            "selected_overdue": overdue,
            "assigned_users": User.objects.all().order_by("username"),
            "assigned_teams": Team.objects.all().order_by("name"),
            "selected_assigned_user": assigned_user,
            "selected_assigned_team": assigned_team,
            "search_query": q,
            "selected_sort": sort,
            "return_url": request.get_full_path(),
            "kanban_columns": kanban_columns,
        },
    )

@login_required
def ticket_create(request):
    next_url = request.POST.get("next") or request.GET.get("next") or reverse("ticket-list")
    if request.method == "POST":
        form = TicketForm(request.POST)

        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.opened_by = request.user
            if ticket.assigned_team and not can_create_team_ticket(request.user, ticket.assigned_team):
                return HttpResponseForbidden(
                    "You do not have permission to create tickets for this team."
                )
            ticket.save()
            messages.success(request, "Ticket created.")
            return redirect(next_url)


    else:
        form = TicketForm()

    return render(
        request,
        "tickets/ticket_form.html",
        {
            "form": form,
            "page_title": "New Ticket",
            "button_text": "Create Ticket",
            "next_url": next_url,
        },
    )

@login_required
def ticket_edit(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    if not can_change_team_ticket_status(request.user, ticket):
        return HttpResponseForbidden("You do not have permission to edit this ticket.")
    old_status = ticket.status
    next_url = request.POST.get("next") or request.GET.get("next") or reverse("ticket-list")

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
            messages.success(request, "Ticket saved.")
            return redirect(next_url)
    else:
        form = TicketForm(instance=ticket)

    return render(
        request,
        "tickets/ticket_form.html",
        {
            "form": form,
            "page_title": "Edit Ticket",
            "button_text": "Save Changes",
            "next_url": next_url,
        },
    )

@login_required
def ticket_delete(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    if not can_delete_team_ticket(request.user, ticket):
        return HttpResponseForbidden("You do not have permission to delete this ticket.")
    next_url = request.POST.get("next") or request.GET.get("next") or reverse("ticket-list")

    if request.method == "POST":
        ticket.delete()
        messages.success(request, "Ticket deleted.")
        return redirect(next_url)

    return render(
        request,
        "tickets/ticket_confirm_delete.html",
        {"ticket": ticket, "next_url": next_url,},
    )

@login_required
def ticket_detail(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    if not can_view_team_ticket(request.user, ticket):
        return HttpResponseForbidden("You do not have permission to view this ticket.")
    next_url = request.GET.get("next") or reverse("ticket-list")
    subtickets = ticket.subtickets.select_related(
        "assigned_user",
        "assigned_team",
    ).order_by("status", "due_date", "title")

    return render(
        request,
        "tickets/ticket_detail.html",
        {"ticket": ticket, "next_url": next_url, "subtickets": subtickets,},
    )

@login_required
def ticket_subticket_create(request, pk):
    parent_ticket = get_object_or_404(Ticket, pk=pk)

    if not can_create_team_subticket(request.user, parent_ticket):
        return HttpResponseForbidden(
            "You do not have permission to create subtickets for this ticket."
        )

    next_url = (
        request.POST.get("next")
        or request.GET.get("next")
        or reverse("ticket-detail", kwargs={"pk": parent_ticket.pk})
    )

    if request.method == "POST":
        form = TicketForm(request.POST)

        if form.is_valid():
            ticket = form.save(commit=False)
            
            parent_team = parent_ticket.get_permission_team()
            child_team = ticket.assigned_team

            if parent_team is not None:
                # This subticket is under an existing team-controlled path.

                if child_team is not None:
                    # Team-assigned subtickets must stay in the same team path.
                    if child_team.id != parent_team.id:
                        return HttpResponseForbidden(
                            "You cannot assign a subticket to a different team than its parent path."
                        )

                    # Making a team-wide subticket is leader-only.
                    if not can_create_team_ticket(request.user, parent_team):
                        return HttpResponseForbidden(
                            "Only team leaders can create team-assigned subtickets."
                        )

            else:
                # This parent path is not team-controlled yet.
                # Assigning the child to a team creates a new team-owned branch, so leader-only.
                if child_team is not None and not can_create_team_ticket(request.user, child_team):
                    return HttpResponseForbidden(
                        "Only team leaders can create team-assigned tickets."
                    )
            ticket.parent = parent_ticket
            ticket.opened_by = request.user
            ticket.save()
            messages.success(request, "Ticket created.")
            detail_url = reverse("ticket-detail", kwargs={"pk": parent_ticket.pk})
            return redirect(f"{detail_url}?{urlencode({'next': next_url})}")
    else:
        form = TicketForm()

    return render(
        request,
        "tickets/ticket_form.html",
        {
            "form": form,
            "next_url": next_url,
            "page_title": f"New subticket for {parent_ticket.title}",
            "button_text": "Create subticket",
        },
    )

@login_required
@require_POST
def ticket_status_update(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)

    if not can_change_team_ticket_status(request.user, ticket):
        return JsonResponse(
            {"ok": False, "message": "You do not have permission to update this ticket."},
            status=403,
        )

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse(
            {"ok": False, "message": "Invalid request body."},
            status=400,
        )

    new_status = data.get("status")
    actual_time = data.get("actual_time")

    valid_statuses = {value for value, label in Ticket.Status.choices}

    if new_status not in valid_statuses:
        return JsonResponse(
            {"ok": False, "message": "Invalid status."},
            status=400,
        )

    old_status = ticket.status
    ticket.status = new_status

    if new_status == Ticket.Status.CLOSED:
        ticket.closed_by = request.user

        if actual_time in ("", None):
            return JsonResponse(
                {"ok": False, "message": "Actual time is required when closing a ticket."},
                status=400,
            )

        try:
            ticket.actual_time = int(actual_time)
        except (TypeError, ValueError):
            return JsonResponse(
                {"ok": False, "message": "Actual time must be a number of minutes."},
                status=400,
            )
    else:
        ticket.closed_by = None
        ticket.actual_time = None

    try:
        ticket.full_clean()
    except ValidationError as error:
        return JsonResponse(
            {
                "ok": False,
                "message": "Ticket could not be updated.",
                "errors": error.message_dict,
            },
            status=400,
        )

    ticket.save()

    return JsonResponse({
        "ok": True,
        "message": f"Moved ticket to {ticket.get_status_display()}.",
        "ticket": {
            "id": ticket.pk,
            "status": ticket.status,
            "status_display": ticket.get_status_display(),
            "old_status": old_status,
        },
    })