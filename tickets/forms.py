from django import forms

from .models import Ticket
from django.contrib.auth import get_user_model
from teams.models import Team


class TicketForm(forms.ModelForm):
    due_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d",),
        input_formats=["%Y-%m-%d"],
    )
    class Meta:
        model = Ticket
        fields = [
            "title",
            "description",
            "status",
            "assigned_team",
            "assigned_user",
            "due_date",
            "priority",
            "estimated_time",
            "actual_time"
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        required_fields = [
            "title",
            "description",
            "status",
            "priority",
            "due_date",
        ]

        for field_name in required_fields:
            self.fields[field_name].required = True
        
        self.fields["assigned_user"].required = False
        self.fields["assigned_team"].required = False

        
        self.fields["assigned_user"].queryset = (
            get_user_model().objects.all().order_by("username")
        )

    def clean(self):
        cleaned_data = super().clean()

        assigned_user = cleaned_data.get("assigned_user")
        assigned_team = cleaned_data.get("assigned_team")

        if bool(assigned_user) == bool(assigned_team):
            raise forms.ValidationError(
                "Choose exactly one assignee: either a user or a team."
            )

        return cleaned_data