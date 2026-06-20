from django.core.management.base import BaseCommand

from tickets.models import NotificationDelivery
from tickets.notifications import send_notification_delivery


class Command(BaseCommand):
    help = "Send pending notification deliveries."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50)
        parser.add_argument(
            "--retry-failed",
            action="store_true",
            help="Also retry failed deliveries.",
        )
        parser.add_argument(
            "--max-attempts",
            type=int,
            default=3,
            help="Maximum attempts before skipping a delivery.",
        )

    def handle(self, *args, **options):
        statuses = [NotificationDelivery.Status.PENDING]

        if options["retry_failed"]:
            statuses.append(NotificationDelivery.Status.FAILED)

        deliveries = NotificationDelivery.objects.filter(
            status__in=statuses,
            attempts__lt=options["max_attempts"],
        ).select_related(
            "event",
            "event__ticket",
            "event__actor",
            "channel",
        ).order_by(
            "created_at",
        )[: options["limit"]]

        processed = 0
        sent = 0
        failed = 0

        for delivery in deliveries:
            processed += 1

            if send_notification_delivery(delivery):
                sent += 1
            else:
                failed += 1

        self.stdout.write(f"Processed: {processed}")
        self.stdout.write(self.style.SUCCESS(f"Sent: {sent}"))

        if failed:
            self.stdout.write(self.style.WARNING(f"Failed: {failed}"))
        else:
            self.stdout.write("Failed: 0")