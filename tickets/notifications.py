import json
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError

from django.utils import timezone

from .models import NotificationChannel, NotificationDelivery


def build_ticket_event_payload(event):
    actor = event.actor.username if event.actor else "System"

    return {
        "event_type": event.event_type,
        "event_label": event.get_event_type_display(),
        "ticket": {
            "id": event.ticket_id,
            "title": event.ticket.title,
            "status": event.ticket.status,
            "status_display": event.ticket.get_status_display(),
        },
        "actor": actor,
        "old_values": event.old_values,
        "new_values": event.new_values,
        "created_at": event.created_at.isoformat(),
    }


def build_ticket_event_text(event):
    actor = event.actor.username if event.actor else "System"
    ticket = event.ticket

    if event.event_type == "ticket.created":
        return f'{actor} created ticket "{ticket.title}".'

    if event.event_type == "ticket.updated":
        changed_fields = ", ".join(event.new_values.keys())

        if changed_fields:
            return f'{actor} updated ticket "{ticket.title}" fields: {changed_fields}.'

        return f'{actor} updated ticket "{ticket.title}".'

    if event.event_type == "ticket.closed":
        return f'{actor} closed ticket "{ticket.title}".'

    if event.event_type == "ticket.reopened":
        return f'{actor} reopened ticket "{ticket.title}".'

    if event.event_type == "ticket.status_changed":
        old_status = event.old_values.get("status_display", "Unknown")
        new_status = event.new_values.get("status_display", "Unknown")
        return f'{actor} moved ticket "{ticket.title}" from {old_status} to {new_status}.'

    if event.event_type == "ticket.reference_added":
        external_id = event.new_values.get("external_id", "a reference")
        integration_name = event.new_values.get("integration_token_name")

        if integration_name:
            return f'Integration "{integration_name}" added reference {external_id} to ticket "{ticket.title}".'

        return f'{actor} added reference {external_id} to ticket "{ticket.title}".'

    if event.event_type == "ticket.assigned":
        assignee = event.new_values.get("assignee")

        if assignee is None:
            return f'{actor} unassigned ticket "{ticket.title}".'

        assignee_type = assignee.get("type")
        assignee_name = assignee.get("name", "Unknown")

        if assignee_type == "user":
            return f'{actor} assigned ticket "{ticket.title}" to {assignee_name}.'

        if assignee_type == "team":
            return f'{actor} assigned ticket "{ticket.title}" to team {assignee_name}.'

        return f'{actor} changed the assignee for ticket "{ticket.title}".'

    return f'{actor} triggered {event.get_event_type_display()} on ticket "{ticket.title}".'


def send_discord_webhook(delivery):
    channel = delivery.channel
    event = delivery.event

    if not channel.webhook_url:
        raise ValueError("Notification channel has no webhook URL.")

    payload = {
        "content": build_ticket_event_text(event),
        "embeds": [
            {
                "title": event.ticket.title,
                "description": event.get_event_type_display(),
                "fields": [
                    {
                        "name": "Ticket ID",
                        "value": str(event.ticket_id),
                        "inline": True,
                    },
                    {
                        "name": "Status",
                        "value": event.ticket.get_status_display(),
                        "inline": True,
                    },
                ],
            }
        ],
    }

    body = json.dumps(payload).encode("utf-8")

    req = urllib_request.Request(
        channel.webhook_url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "django-ticket-tracker",
        },
        method="POST",
    )

    with urllib_request.urlopen(req, timeout=10) as response:
        if response.status >= 400:
            raise ValueError(f"Discord webhook returned HTTP {response.status}.")

def send_generic_webhook(delivery):
    channel = delivery.channel
    event = delivery.event

    if not channel.webhook_url:
        raise ValueError("Notification channel has no webhook URL.")

    payload = {
        "text": build_ticket_event_text(event),
        "event": build_ticket_event_payload(event),
    }

    body = json.dumps(payload).encode("utf-8")

    req = urllib_request.Request(
        channel.webhook_url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "django-ticket-tracker",
        },
        method="POST",
    )

    with urllib_request.urlopen(req, timeout=10) as response:
        if response.status >= 400:
            raise ValueError(f"Webhook returned HTTP {response.status}.")


def send_notification_delivery(delivery):
    delivery.attempts += 1

    try:
        if delivery.channel.provider == NotificationChannel.Provider.WEBHOOK:
            send_generic_webhook(delivery)
        elif delivery.channel.provider == NotificationChannel.Provider.DISCORD:
            send_discord_webhook(delivery)
        else:
            raise ValueError(
                f"Provider {delivery.channel.provider} is not implemented yet."
            )
    except (HTTPError, URLError, TimeoutError, ValueError) as error:
        delivery.status = NotificationDelivery.Status.FAILED
        delivery.last_error = str(error)
        delivery.save(update_fields=[
            "status",
            "attempts",
            "last_error",
        ])
        return False

    delivery.status = NotificationDelivery.Status.SENT
    delivery.last_error = ""
    delivery.sent_at = timezone.now()
    delivery.save(update_fields=[
        "status",
        "attempts",
        "last_error",
        "sent_at",
    ])
    return True

def send_pending_deliveries_for_event(event):
    deliveries = event.notification_deliveries.filter(
        status=NotificationDelivery.Status.PENDING,
    ).select_related(
        "event",
        "event__ticket",
        "event__actor",
        "channel",
    )

    results = []

    for delivery in deliveries:
        results.append(send_notification_delivery(delivery))

    return results