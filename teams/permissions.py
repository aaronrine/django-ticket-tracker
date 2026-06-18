from .models import TeamMembership


def get_team_role(user, team):
    if not user.is_authenticated:
        return TeamMembership.Role.RESTRICTED

    membership = TeamMembership.objects.filter(
        team=team,
        user=user,
    ).first()

    if membership is None:
        # Non-members can read team-owned tickets by default.
        return TeamMembership.Role.READ_ONLY

    return membership.role


def can_view_team_ticket(user, ticket):
    if ticket.assigned_team is None:
        return True

    role = get_team_role(user, ticket.assigned_team)

    return role in {
        TeamMembership.Role.LEADER,
        TeamMembership.Role.NORMAL,
        TeamMembership.Role.READ_ONLY,
    }


def can_change_team_ticket_status(user, ticket):
    if ticket.assigned_team is None:
        return True

    role = get_team_role(user, ticket.assigned_team)

    return role in {
        TeamMembership.Role.LEADER,
        TeamMembership.Role.NORMAL,
    }


def can_delete_team_ticket(user, ticket):
    if ticket.assigned_team is None:
        return True

    role = get_team_role(user, ticket.assigned_team)

    return role == TeamMembership.Role.LEADER


def can_create_team_ticket(user, team):
    role = get_team_role(user, team)

    return role == TeamMembership.Role.LEADER


def can_create_team_subticket(user, parent_ticket):
    if parent_ticket.assigned_team is None:
        return True

    role = get_team_role(user, parent_ticket.assigned_team)

    return role in {
        TeamMembership.Role.LEADER,
        TeamMembership.Role.NORMAL,
    }