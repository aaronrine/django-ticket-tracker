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

    if "status" not in request.GET:
        status = Ticket.Status.OPEN

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
            "assigned_users": User.objects.all().order_by("username"),
            "assigned_teams": Team.objects.all().order_by("name"),
            "selected_assigned_user": assigned_user,
            "selected_assigned_team": assigned_team,
            "search_query": q,
            "selected_sort": sort,
            "query_params": query_params.urlencode(),
            "return_url": request.get_full_path(),
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