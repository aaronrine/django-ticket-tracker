from django import forms

from .models import Ticket
from django.contrib.auth import get_user_model


class TicketForm(forms.ModelForm):
    due_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    class Meta:
        model = Ticket
        fields = ["title", "description", "status", "assignees", "due_date", "priority"]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        required_fields = [
            "title",
            "description",
            "status",
            "priority",
            "due_date",
            "assignees",
        ]

        for field_name in required_fields:
            self.fields[field_name].required = True
        
        self.fields["assignees"].queryset = get_user_model().objects.all().order_by("username")