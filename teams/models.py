from django.conf import settings
from django.db import models
from django.db.models import Q


class Team(models.Model):
    name = models.CharField(
        max_length=100,
        unique=True,
    )

    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="TeamMembership",
        related_name="member_teams",
    )

    def __str__(self):
        return self.name


class TeamMembership(models.Model):
    class Role(models.TextChoices):
        LEADER = "leader", "Leader"
        NORMAL = "member", "Normal"
        READ_ONLY = "read_only", "Read_Only"
        RESTRICTED = "restricted", "Restricted"

    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="memberships",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="team_memberships",
    )

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.NORMAL,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["team", "user"],
                name="unique_team_member",
            ),
            models.UniqueConstraint(
                fields=["team"],
                condition=Q(role="leader"),
                name="unique_team_leader",
            ),
        ]

    def __str__(self):
        return f"{self.user} - {self.team} ({self.role})"