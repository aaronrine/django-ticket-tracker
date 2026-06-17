from django import forms

from .models import UserProfile


TIMEZONE_CHOICES = [
    ("America/Los_Angeles", "Pacific Time"),
    ("America/Denver", "Mountain Time"),
    ("America/Chicago", "Central Time"),
    ("America/New_York", "Eastern Time"),
    ("UTC", "UTC"),
]


class UserProfileForm(forms.ModelForm):
    timezone = forms.ChoiceField(choices=TIMEZONE_CHOICES)

    class Meta:
        model = UserProfile
        fields = ["timezone"]