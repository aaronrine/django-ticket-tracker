from django.core.management.base import BaseCommand

from tickets.models import NotificationDelivery
from tickets.notifications import send_notification_delivery


class Command(BaseCommand):
    help = "Send pending notification deliveries."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=25,
            help="Maximum number of pending deliveries to process.",
        )

    def handle(self, *args, **options):
        limit = options["limit"]

        deliveries = NotificationDelivery.objects.filter(
            status=NotificationDelivery.Status.PENDING,
        ).select_related(
            "event",
            "event__ticket",
            "event__actor",
            "channel",
        ).order_by("created_at")[:limit]

        sent_count = 0
        failed_count = 0

        for delivery in deliveries:
            was_sent = send_notification_delivery(delivery)

            if was_sent:
                sent_count += 1
            else:
                failed_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Processed {sent_count + failed_count} deliveries: "
                f"{sent_count} sent, {failed_count} failed."
            )
        )