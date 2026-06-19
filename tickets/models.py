from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.core.validators import MinValueValidator


class Ticket(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In Progress"
        CLOSED = "closed", "Closed"
    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
    

    title = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="subtickets",
    )
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=False,
        related_name="opened_tickets",
    )

    assigned_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="assigned_tickets",
    )

    assigned_team = models.ForeignKey(
        "teams.Team",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="assigned_tickets",
    )

    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="closed_tickets",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.MEDIUM,
    )
    due_date = models.DateField()
    estimated_time = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Estimated time to complete, in minutes.",
    )
    actual_time = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Actual time to complete, in minutes.",
    )

    def clean(self):
        super().clean()

        has_user = self.assigned_user is not None
        has_team = self.assigned_team is not None

        if has_user == has_team:
            raise ValidationError(
                "A ticket must be assigned to exactly one user or one team."
            )
        if self.actual_minutes is not None and self.status != self.Status.CLOSED:
            raise ValidationError({
                "actual_minutes": "Actual time can only be set when the ticket is closed."
            })

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(assigned_user__isnull=False, assigned_team__isnull=True)
                    | Q(assigned_user__isnull=True, assigned_team__isnull=False)
                ),
                name="ticket_exactly_one_assignment",
            )
        ]

    def __str__(self):
        return self.title

    @property
    def is_overdue(self):
        if not self.due_date:
            return False

        if self.status == self.Status.CLOSED:
            return False

        return self.due_date < timezone.localdate()

    def get_permission_team(self):
        ticket = self
        seen_ids = set()

        while ticket is not None:
            if ticket.pk in seen_ids:
                return None

            seen_ids.add(ticket.pk)

            if ticket.assigned_team_id is not None:
                return ticket.assigned_team

            ticket = ticket.parent

        return None
    
    @property
    def estimated_time_display(self):
        return format_minutes(self.estimated_time)

    @property
    def actual_time_display(self):
        return format_minutes(self.actual_time)

def format_minutes(minutes):
    if minutes is None:
        return "Not set"

    if minutes < 60:
        return f"{minutes} min"

    hours, minutes = divmod(minutes, 60)

    if hours < 24:
        if minutes:
            return f"{hours} hr {minutes} min"
        return f"{hours} hr"

    days, hours = divmod(hours, 24)

    if days < 7:
        if hours:
            return f"{days} day {hours} hr"
        return f"{days} day"

    weeks, days = divmod(days, 7)

    if days:
        return f"{weeks} week {days} day"
    return f"{weeks} week"