from django.core.management.base import BaseCommand, CommandError

from teams.models import Team
from tickets.models import IntegrationToken


class Command(BaseCommand):
    help = "Manage integration tokens."

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(dest="action", required=True)

        generate = subparsers.add_parser("generate")
        generate.add_argument("--team-id", type=int, required=True)
        generate.add_argument("--name", required=True)

        list_tokens = subparsers.add_parser("list")
        list_tokens.add_argument("--team-id", type=int)
        list_tokens.add_argument("--include-inactive", action="store_true")

        revoke = subparsers.add_parser("revoke")
        target = revoke.add_mutually_exclusive_group(required=True)
        target.add_argument("--id", type=int)
        target.add_argument("--prefix")
        target.add_argument("--token")

    def handle(self, *args, **options):
        action = options["action"]

        if action == "generate":
            self.generate_token(options)
        elif action == "list":
            self.list_tokens(options)
        elif action == "revoke":
            self.revoke_token(options)
        else:
            raise CommandError(f"Unknown action: {action}")

    def generate_token(self, options):
        try:
            team = Team.objects.get(pk=options["team_id"])
        except Team.DoesNotExist:
            raise CommandError("Team not found.")

        token, raw_token = IntegrationToken.create_token(
            team=team,
            name=options["name"],
        )

        self.stdout.write(self.style.SUCCESS("Integration token created."))
        self.stdout.write("")
        self.stdout.write(f"ID: {token.id}")
        self.stdout.write(f"Team: {team.name}")
        self.stdout.write(f"Name: {token.name}")
        self.stdout.write(f"Prefix: {token.token_prefix}")
        self.stdout.write("")
        self.stdout.write(self.style.WARNING("Raw token. Copy this now; it will not be shown again:"))
        self.stdout.write(raw_token)

    def list_tokens(self, options):
        tokens = IntegrationToken.objects.select_related("team").order_by(
            "team__name",
            "name",
            "id",
        )

        if options.get("team_id"):
            tokens = tokens.filter(team_id=options["team_id"])

        if not options.get("include_inactive"):
            tokens = tokens.filter(is_active=True)

        if not tokens.exists():
            self.stdout.write("No tokens found.")
            return

        for token in tokens:
            status = "active" if token.is_active else "inactive"
            last_used = token.last_used_at or "never"

            self.stdout.write(
                f"{token.id} | {status} | {token.team.name} | "
                f"{token.name} | prefix={token.token_prefix} | last_used={last_used}"
            )

    def revoke_token(self, options):
        token = self.get_token_for_revoke(options)

        if not token.is_active:
            self.stdout.write(self.style.WARNING("Token is already inactive."))
            return

        token.is_active = False
        token.save(update_fields=["is_active"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Revoked token {token.id} ({token.name}) for {token.team.name}."
            )
        )

    def get_token_for_revoke(self, options):
        if options.get("id"):
            try:
                return IntegrationToken.objects.select_related("team").get(
                    pk=options["id"]
                )
            except IntegrationToken.DoesNotExist:
                raise CommandError("Token not found.")

        if options.get("token"):
            token_hash = IntegrationToken.hash_token(options["token"])

            try:
                return IntegrationToken.objects.select_related("team").get(
                    token_hash=token_hash
                )
            except IntegrationToken.DoesNotExist:
                raise CommandError("Token not found.")

        if options.get("prefix"):
            matches = IntegrationToken.objects.select_related("team").filter(
                token_prefix=options["prefix"]
            )

            count = matches.count()

            if count == 0:
                raise CommandError("Token not found.")

            if count > 1:
                raise CommandError(
                    "Multiple tokens match that prefix. Revoke by --id instead."
                )

            return matches.get()

        raise CommandError("No revoke target provided.")