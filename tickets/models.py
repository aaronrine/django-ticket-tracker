from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


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

    def clean(self):
        super().clean()

        has_user = self.assigned_user is not None
        has_team = self.assigned_team is not None

        if has_user == has_team:
            raise ValidationError(
                "A ticket must be assigned to exactly one user or one team."
            )

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