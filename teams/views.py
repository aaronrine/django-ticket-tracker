from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Count, Exists, OuterRef
from .forms import AddTeamMemberForm
from django.contrib.auth import get_user_model
from .models import Team, TeamMembership
from django.urls import reverse
from urllib.parse import urlencode


@login_required
def team_list(request):
    User = get_user_model()

    q = request.GET.get("q", "").strip()
    member = request.GET.get("member", "")
    membership = request.GET.get("membership", "")
    sort = request.GET.get("sort", "name")

    teams = Team.objects.annotate(
        member_count=Count("memberships", distinct=True),
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

    if q:
        teams = teams.filter(name__icontains=q)

    if member:
        teams = teams.filter(memberships__user_id=member)

    if membership == "mine":
        teams = teams.filter(memberships__user=request.user)
    elif membership == "leading":
        teams = teams.filter(
            memberships__user=request.user,
            memberships__role=TeamMembership.Role.LEADER,
        )

    allowed_sorts = {
        "name": "name",
        "-name": "-name",
        "member_count": "-member_count",
    }

    teams = teams.prefetch_related("members").order_by(
        allowed_sorts.get(sort, "name")
    )

    members = (
        User.objects.filter(team_memberships__isnull=False)
        .distinct()
        .order_by("username")
    )

    return render(
        request,
        "teams/team_list.html",
        {
            "teams": teams,
            "members": members,
            "selected_q": q,
            "selected_member": member,
            "selected_membership": membership,
            "selected_sort": sort,
            "return_url": request.get_full_path(),
        },
    )


@login_required
def team_manage(request, pk):
    team = get_object_or_404(
        Team,
        pk=pk,
        memberships__user=request.user,
        memberships__role=TeamMembership.Role.LEADER,
    )

    next_url = request.POST.get("next") or request.GET.get("next") or reverse("teams:team-list")
    manage_url = (
    reverse("teams:team-manage", kwargs={"pk": team.pk})
    + "?"
    + urlencode({"next": next_url})
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
                return redirect(manage_url)

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

            return redirect(manage_url)

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
        "next_url": next_url
    })