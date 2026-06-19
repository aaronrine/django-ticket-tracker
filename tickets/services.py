from django.core.exceptions import ValidationError

from .models import (
    Ticket,
    TicketEvent,
    NotificationRule,
    NotificationDelivery,
)


def create_ticket_event(
    *,
    ticket,
    actor,
    event_type,
    old_values=None,
    new_values=None,
):
    event = TicketEvent.objects.create(
        ticket=ticket,
        actor=actor,
        event_type=event_type,
        old_values=old_values or {},
        new_values=new_values or {},
    )

    team = ticket.get_permission_team()

    if team is None:
        return event

    rules = NotificationRule.objects.filter(
        team=team,
        event_type=event_type,
        is_active=True,
        channel__is_active=True,
    ).select_related("channel")

    seen_channel_ids = set()

    for rule in rules:
        if rule.channel_id in seen_channel_ids:
            continue

        seen_channel_ids.add(rule.channel_id)

        NotificationDelivery.objects.create(
            event=event,
            channel=rule.channel,
        )

    return event

def format_ticket_assignee(*, assigned_user=None, assigned_team=None):
    if assigned_user is not None:
        return {
            "type": "user",
            "id": assigned_user.id,
            "name": assigned_user.username,
        }

    if assigned_team is not None:
        return {
            "type": "team",
            "id": assigned_team.id,
            "name": assigned_team.name,
        }

    return None


def create_assignment_event_if_changed(
    *,
    ticket,
    actor,
    old_assigned_user=None,
    old_assigned_team=None,
):
    old_values = format_ticket_assignee(
        assigned_user=old_assigned_user,
        assigned_team=old_assigned_team,
    )

    new_values = format_ticket_assignee(
        assigned_user=ticket.assigned_user,
        assigned_team=ticket.assigned_team,
    )

    if old_values == new_values:
        return None

    return create_ticket_event(
        ticket=ticket,
        actor=actor,
        event_type=TicketEvent.Type.ASSIGNED,
        old_values={
            "assignee": old_values,
        },
        new_values={
            "assignee": new_values,
        },
    )

def serialize_ticket_update_fields(ticket):
    return {
        "title": ticket.title,
        "description": ticket.description,
        "priority": ticket.priority,
        "due_date": ticket.due_date.isoformat() if ticket.due_date else None,
        "estimated_time": ticket.estimated_time,
    }


def create_ticket_updated_event_if_changed(*, ticket, actor, old_values):
    new_values = serialize_ticket_update_fields(ticket)

    changed_old_values = {}
    changed_new_values = {}

    for field, old_value in old_values.items():
        new_value = new_values.get(field)

        if old_value != new_value:
            changed_old_values[field] = old_value
            changed_new_values[field] = new_value

    if not changed_old_values:
        return None

    return create_ticket_event(
        ticket=ticket,
        actor=actor,
        event_type=TicketEvent.Type.UPDATED,
        old_values=changed_old_values,
        new_values=changed_new_values,
    )

def update_ticket_status(*, ticket, user, new_status, actual_time=None, old_status=None):
    if old_status is None:
        old_status = ticket.status

    old_status_display = ticket.get_status_display()

    ticket.status = new_status

    if new_status == Ticket.Status.CLOSED:
        if old_status != Ticket.Status.CLOSED:
            ticket.closed_by = user

        if actual_time in ("", None):
            raise ValidationError({
                "actual_time": "Actual time is required when closing a ticket."
            })

        ticket.actual_time = int(actual_time)
    else:
        if old_status == Ticket.Status.CLOSED:
            ticket.closed_by = None

        ticket.actual_time = None

    ticket.full_clean()
    ticket.save()

    if old_status != new_status:
        if new_status == Ticket.Status.CLOSED:
            event_type = TicketEvent.Type.CLOSED
        elif old_status == Ticket.Status.CLOSED:
            event_type = TicketEvent.Type.REOPENED
        else:
            event_type = TicketEvent.Type.STATUS_CHANGED

        create_ticket_event(
            ticket=ticket,
            actor=user,
            event_type=event_type,
            old_values={
                "status": old_status,
                "status_display": old_status_display,
            },
            new_values={
                "status": ticket.status,
                "status_display": ticket.get_status_display(),
            },
        )

    return old_status, ticket