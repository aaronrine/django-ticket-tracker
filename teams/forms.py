from django import forms
from django.contrib.auth import get_user_model

from .models import TeamMembership


class AddTeamMemberForm(forms.Form):
    user = forms.ModelChoiceField(
        queryset=get_user_model().objects.none(),
        required=True,
        label="User",
    )

    def __init__(self, *args, team=None, **kwargs):
        super().__init__(*args, **kwargs)

        User = get_user_model()

        queryset = User.objects.all().order_by("username")

        if team is not None:
            queryset = queryset.exclude(
                team_memberships__team=team
            )

        self.fields["user"].queryset = queryset

class ChangeTeamMemberRoleForm(forms.Form):
    role = forms.ChoiceField(
        choices=[
            (TeamMembership.Role.NORMAL, "Normal"),
            (TeamMembership.Role.READ_ONLY, "Read-only"),
            (TeamMembership.Role.RESTRICTED, "Restricted"),
        ],
        required=True,
    )