from django import forms

from .models import Ticket


class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ["title", "description", "status", "assignees", "due_date", "priority"]
        widgets = {"due_date": forms.DateInput(attrs={"type": "date"}),}