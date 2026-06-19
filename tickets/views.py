from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from .forms import TicketForm, TicketReferenceForm
from .models import Ticket, TicketEvent, IntegrationToken, TicketReference
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.core.paginator import Paginator
from teams.models import Team
from django.http import HttpResponseForbidden
from urllib.parse import urlencode
from django.contrib import messages
import json
from .services import (
    update_ticket_status,
    create_ticket_event,
    create_assignment_event_if_changed,
    serialize_ticket_update_fields,
    create_ticket_updated_event_if_changed,
)
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
            create_ticket_event(
                ticket=ticket,
                actor=request.user,
                event_type=TicketEvent.Type.CREATED,
                new_values={
                    "title": ticket.title,
                    "status": ticket.status,
                    "status_display": ticket.get_status_display(),
                    "priority": ticket.priority,
                    "priority_display": ticket.get_priority_display(),
                },
            )
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
    old_assigned_user = ticket.assigned_user
    old_assigned_team = ticket.assigned_team
    old_update_values = serialize_ticket_update_fields(ticket)
    next_url = request.POST.get("next") or request.GET.get("next") or reverse("ticket-list")

    if request.method == "POST":
        form = TicketForm(request.POST, instance=ticket)

        if form.is_valid():
            updated_ticket = form.save(commit=False)

            try:
                update_ticket_status(
                    ticket=updated_ticket,
                    user=request.user,
                    new_status=updated_ticket.status,
                    actual_time=updated_ticket.actual_time,
                    old_status=old_status,
                )
            except ValidationError as error:
                toast_message = "Ticket could not be saved."

                if hasattr(error, "message_dict"):
                    for field, messages_for_field in error.message_dict.items():
                        form_field = field if field in form.fields else None

                        for message in messages_for_field:
                            form.add_error(form_field, message)

                        if messages_for_field:
                            toast_message = messages_for_field[0]
                else:
                    for message in error.messages:
                        form.add_error(None, message)

                    if error.messages:
                        toast_message = error.messages[0]

                messages.error(request, toast_message)
            else:
                create_assignment_event_if_changed(
                    ticket=updated_ticket,
                    actor=request.user,
                    old_assigned_user=old_assigned_user,
                    old_assigned_team=old_assigned_team,
                )
                create_ticket_updated_event_if_changed(
                    ticket=updated_ticket,
                    actor=request.user,
                    old_values=old_update_values,
                )
                messages.success(request, "Ticket saved.")
                return redirect(next_url)
        else:
            messages.error(request, "Ticket could not be saved. Please check the form.")
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

    references = ticket.references.order_by("-created_at")

    return render(
        request,
        "tickets/ticket_detail.html",
        {
            "ticket": ticket,
            "next_url": next_url,
            "subtickets": subtickets,
            "references": references,
        },
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
            create_ticket_event(
                ticket=ticket,
                actor=request.user,
                event_type=TicketEvent.Type.CREATED,
                new_values={
                    "title": ticket.title,
                    "status": ticket.status,
                    "status_display": ticket.get_status_display(),
                    "priority": ticket.priority,
                    "priority_display": ticket.get_priority_display(),
                },
            )
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

    try:
        old_status, ticket = update_ticket_status(
            ticket=ticket,
            user=request.user,
            new_status=new_status,
            actual_time=actual_time,
        )
    except (ValidationError, TypeError, ValueError) as error:
        if isinstance(error, ValidationError) and hasattr(error, "message_dict"):
            first_messages = next(iter(error.message_dict.values()))
            message = first_messages[0] if first_messages else "Ticket could not be updated."
            errors = error.message_dict
        elif isinstance(error, ValidationError):
            message = error.messages[0] if error.messages else "Ticket could not be updated."
            errors = {}
        else:
            message = "Actual time must be a number of minutes."
            errors = {}

        return JsonResponse(
            {
                "ok": False,
                "message": message,
                "errors": errors,
            },
            status=400,
        )

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

@login_required
def ticket_reference_create(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)

    if not can_change_team_ticket_status(request.user, ticket):
        return HttpResponseForbidden(
            "You do not have permission to add references to this ticket."
        )

    next_url = (
        request.POST.get("next")
        or request.GET.get("next")
        or reverse("ticket-detail", kwargs={"pk": ticket.pk})
    )

    if request.method == "POST":
        form = TicketReferenceForm(request.POST)

        if form.is_valid():
            reference = form.save(commit=False)
            reference.ticket = ticket
            reference.save()

            create_ticket_event(
                ticket=ticket,
                actor=request.user,
                event_type=TicketEvent.Type.REFERENCE_ADDED,
                new_values={
                    "reference_id": reference.pk,
                    "kind": reference.kind,
                    "kind_display": reference.get_kind_display(),
                    "provider": reference.provider,
                    "provider_display": reference.get_provider_display(),
                    "external_id": reference.external_id,
                    "url": reference.url,
                    "title": reference.title,
                },
            )

            messages.success(request, "Reference added.")
            return redirect(next_url)
    else:
        form = TicketReferenceForm(initial={
            "provider": "manual",
            "kind": "commit",
        })

    return render(
        request,
        "tickets/ticket_reference_form.html",
        {
            "form": form,
            "ticket": ticket,
            "next_url": next_url,
        },
    )

def get_bearer_token(request):
    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        return None

    return auth_header.removeprefix("Bearer ").strip()


def authenticate_integration_request(request):
    raw_token = get_bearer_token(request)

    if not raw_token:
        return None

    token_hash = IntegrationToken.hash_token(raw_token)

    try:
        token = IntegrationToken.objects.select_related("team").get(
            token_hash=token_hash,
            is_active=True,
        )
    except IntegrationToken.DoesNotExist:
        return None

    token.mark_used()
    return token

@csrf_exempt
@require_POST
def integration_ticket_reference_create(request):
    token = authenticate_integration_request(request)

    if token is None:
        return JsonResponse(
            {"ok": False, "message": "Invalid or missing integration token."},
            status=401,
        )

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse(
            {"ok": False, "message": "Invalid JSON body."},
            status=400,
        )

    ticket_id = data.get("ticket_id")

    if not ticket_id:
        return JsonResponse(
            {"ok": False, "message": "ticket_id is required."},
            status=400,
        )

    ticket = get_object_or_404(Ticket, pk=ticket_id)

    ticket_team = ticket.get_permission_team()

    if ticket_team is None or ticket_team.id != token.team_id:
        return JsonResponse(
            {"ok": False, "message": "Token does not have access to this ticket."},
            status=403,
        )

    kind = data.get("kind", TicketReference.Kind.COMMIT)
    provider = data.get("provider", TicketReference.Provider.CUSTOM)
    external_id = data.get("external_id")
    url = data.get("url", "")
    title = data.get("title", "")
    metadata = data.get("metadata", {})

    if not external_id:
        return JsonResponse(
            {"ok": False, "message": "external_id is required."},
            status=400,
        )

    valid_kinds = {value for value, label in TicketReference.Kind.choices}
    valid_providers = {value for value, label in TicketReference.Provider.choices}

    if kind not in valid_kinds:
        return JsonResponse(
            {"ok": False, "message": "Invalid reference kind."},
            status=400,
        )

    if provider not in valid_providers:
        return JsonResponse(
            {"ok": False, "message": "Invalid reference provider."},
            status=400,
        )

    reference = TicketReference.objects.create(
        ticket=ticket,
        kind=kind,
        provider=provider,
        external_id=external_id,
        url=url,
        title=title,
        metadata=metadata,
    )

    create_ticket_event(
        ticket=ticket,
        actor=None,
        event_type=TicketEvent.Type.REFERENCE_ADDED,
        new_values={
            "reference_id": reference.pk,
            "kind": reference.kind,
            "kind_display": reference.get_kind_display(),
            "provider": reference.provider,
            "provider_display": reference.get_provider_display(),
            "external_id": reference.external_id,
            "url": reference.url,
            "title": reference.title,
        },
    )

    return JsonResponse({
        "ok": True,
        "message": "Reference added.",
        "reference": {
            "id": reference.pk,
            "ticket_id": ticket.pk,
            "kind": reference.kind,
            "provider": reference.provider,
            "external_id": reference.external_id,
            "url": reference.url,
            "title": reference.title,
        },
    })