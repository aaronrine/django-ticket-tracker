from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from teams.models import Team


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

        if self.status == self.Status.CLOSED and self.actual_time is None:
            raise ValidationError({
                "actual_time": "Actual time is required when closing a ticket."
            })

        if self.status != self.Status.CLOSED and self.actual_time is not None:
            raise ValidationError({
                "actual_time": "Actual time can only be set when the ticket is closed."
            })

        if (
            self.status == self.Status.CLOSED
            and self.requires_reference_on_close()
            and not self.has_references()
        ):
            raise ValidationError({
                "status": "This team's policy requires at least one reference before closing this ticket."
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

    def get_ticket_policy(self):
        team = self.get_permission_team()

        if team is None:
            return None

        try:
            return team.ticket_policy
        except TeamTicketPolicy.DoesNotExist:
            return None


    def requires_reference_on_close(self):
        policy = self.get_ticket_policy()

        return bool(policy and policy.require_reference_on_close)


    def has_references(self):
        if not self.pk:
            return False

        return self.references.exists()
    
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

class TicketReference(models.Model):
    class Kind(models.TextChoices):
        COMMIT = "commit", "Commit"
        PULL_REQUEST = "pull_request", "Pull Request"
        MERGE_REQUEST = "merge_request", "Merge Request"
        CHANGESET = "changeset", "Changeset"
        CUSTOM = "custom", "Custom"

    class Provider(models.TextChoices):
        MANUAL = "manual", "Manual"
        GITHUB = "github", "GitHub"
        GITLAB = "gitlab", "GitLab"
        BITBUCKET = "bitbucket", "Bitbucket"
        AZURE_DEVOPS = "azure_devops", "Azure DevOps"
        CUSTOM = "custom", "Custom"

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="references",
    )

    kind = models.CharField(
        max_length=32,
        choices=Kind.choices,
        default=Kind.COMMIT,
    )

    provider = models.CharField(
        max_length=32,
        choices=Provider.choices,
        default=Provider.MANUAL,
    )

    external_id = models.CharField(
        max_length=255,
        help_text="Commit hash, PR number, changelist ID, or external reference ID.",
    )

    url = models.URLField(blank=True)

    title = models.CharField(
        max_length=255,
        blank=True,
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_kind_display()} {self.external_id}"

class TeamTicketPolicy(models.Model):
    team = models.OneToOneField(
        Team,
        on_delete=models.CASCADE,
        related_name="ticket_policy",
    )

    require_reference_on_close = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Ticket policy for {self.team.name}"


class TicketEvent(models.Model):
    class Type(models.TextChoices):
        CREATED = "ticket.created", "Ticket created"
        UPDATED = "ticket.updated", "Ticket updated"
        STATUS_CHANGED = "ticket.status_changed", "Status changed"
        ASSIGNED = "ticket.assigned", "Ticket assigned"
        CLOSED = "ticket.closed", "Ticket closed"
        REOPENED = "ticket.reopened", "Ticket reopened"
        REFERENCE_ADDED = "ticket.reference_added", "Reference added"

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="events",
    )

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ticket_events",
    )

    event_type = models.CharField(
        max_length=64,
        choices=Type.choices,
    )

    old_values = models.JSONField(default=dict, blank=True)
    new_values = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_event_type_display()} for {self.ticket}"

class NotificationChannel(models.Model):
    class Provider(models.TextChoices):
        SLACK = "slack", "Slack"
        DISCORD = "discord", "Discord"
        TEAMS = "teams", "Microsoft Teams"
        WEBHOOK = "webhook", "Generic Webhook"
        WHATSAPP = "whatsapp", "WhatsApp"

    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="notification_channels",
    )

    provider = models.CharField(
        max_length=32,
        choices=Provider.choices,
    )

    name = models.CharField(max_length=120)

    webhook_url = models.URLField(blank=True)

    config = models.JSONField(default=dict, blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.get_provider_display()})"


class NotificationRule(models.Model):
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="notification_rules",
    )

    channel = models.ForeignKey(
        NotificationChannel,
        on_delete=models.CASCADE,
        related_name="rules",
    )

    event_type = models.CharField(
        max_length=64,
        choices=TicketEvent.Type.choices,
    )

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.team.name}: {self.event_type} -> {self.channel.name}"


class NotificationDelivery(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    event = models.ForeignKey(
        TicketEvent,
        on_delete=models.CASCADE,
        related_name="notification_deliveries",
    )

    channel = models.ForeignKey(
        NotificationChannel,
        on_delete=models.CASCADE,
        related_name="deliveries",
    )

    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )

    attempts = models.PositiveIntegerField(default=0)

    last_error = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.event} -> {self.channel} ({self.status})"