from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    timezone = models.CharField(
        max_length=64,
        default="America/Los_Angeles",
    )

    def __str__(self):
        return f"{self.user.username} profile"