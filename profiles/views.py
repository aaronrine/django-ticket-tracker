from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import UserProfileForm
from .models import UserProfile


@login_required
def profile_edit(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = UserProfileForm(request.POST, instance=profile)

        if form.is_valid():
            form.save()
            return redirect("ticket-list")
    else:
        form = UserProfileForm(instance=profile)

    return render(
        request,
        "profiles/profile_form.html",
        {"form": form},
    )