from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Exists, OuterRef
from .forms import AddTeamMemberForm
from .models import Team, TeamMembership


@login_required
def team_list(request):
    teams = (
        Team.objects.annotate(
            user_is_member=Exists(
                TeamMembership.objects.filter(
                    team=OuterRef("pk"),
                    user=request.user,
                )
            ),
            user_is_leader=Exists(
                TeamMembership.objects.filter(
                    team=OuterRef("pk"),
                    user=request.user,
                    role=TeamMembership.Role.LEADER,
                )
            ),
        )
        .prefetch_related("members")
        .order_by("name")
    )

    return render(request, "teams/team_list.html", {
        "teams": teams,
    })


@login_required
def team_manage(request, pk):
    team = get_object_or_404(
        Team,
        pk=pk,
        memberships__user=request.user,
        memberships__role=TeamMembership.Role.LEADER,
    )

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "add":
            form = AddTeamMemberForm(request.POST, team=team)

            if form.is_valid():
                user = form.cleaned_data["user"]

                TeamMembership.objects.create(
                    team=team,
                    user=user,
                    role=TeamMembership.Role.MEMBER,
                )

                messages.success(request, "Member added.")
                return redirect("teams:team-manage", pk=team.pk)

        elif action == "remove":
            membership = get_object_or_404(
                TeamMembership,
                pk=request.POST.get("membership_id"),
                team=team,
            )

            if membership.role == TeamMembership.Role.LEADER:
                messages.error(request, "You cannot remove the team leader here.")
            else:
                membership.delete()
                messages.success(request, "Member removed.")

            return redirect("teams:team-manage", pk=team.pk)

    else:
        form = AddTeamMemberForm(team=team)

    memberships = team.memberships.select_related("user").order_by(
        "role",
        "user__username",
    )

    return render(request, "teams/team_manage.html", {
        "team": team,
        "memberships": memberships,
        "form": form,
    })