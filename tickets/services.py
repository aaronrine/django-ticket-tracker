from django.core.exceptions import ValidationError

from .models import Ticket


def update_ticket_status(*, ticket, user, new_status, actual_time=None, old_status=None):
    if old_status is None:
        old_status = ticket.status

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

    return old_status, ticket