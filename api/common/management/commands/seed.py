from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import translation
from rest_framework_simplejwt.tokens import AccessToken

from api.seeding import seed_catalogue, seed_demo, seed_staff


class Command(BaseCommand):
    help = (
        "Load the catalogue in az/ru/en, the demo subscriber (994516643342) and the "
        "admin accounts. Safe to run on every start: what already exists is kept."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true", help="Delete and recreate the demo subscriber"
        )
        parser.add_argument(
            "--refresh",
            action="store_true",
            help="Put the seeded catalogue rows back to their initial content",
        )

    def handle(self, *args, **options):
        # Seed data is written in English; the other languages are filled explicitly.
        with translation.override("en"):
            seed_catalogue(refresh=options["refresh"])
            subscriber, created = seed_demo(reset=options["reset"])
            staff = seed_staff()

        self.stdout.write(self.style.SUCCESS("Catalogue: loaded in az, ru and en"))
        if created:
            self.stdout.write(self.style.SUCCESS(f"Demo subscriber: {subscriber.msisdn} created"))
        else:
            self.stdout.write(f"Demo subscriber: {subscriber.msisdn} kept (--reset recreates it)")
        logins = ", ".join(account.msisdn for account in staff)
        self.stdout.write(
            self.style.SUCCESS(f"Admin accounts: {logins} (password: SEED_STAFF_PASSWORD)")
        )
        if settings.DEBUG:
            self.stdout.write(f"Authorization: Bearer {AccessToken.for_user(subscriber)}")
        else:
            self.stdout.write("API token: run `manage.py demo_token` to print one")
