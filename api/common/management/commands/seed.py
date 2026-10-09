from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import translation
from rest_framework_simplejwt.tokens import AccessToken

from api.insights import services as detected
from api.seeding import (
    answer_offers,
    seed_catalogue,
    seed_crowd,
    seed_demo,
    seed_staff,
    seed_test_numbers,
)
from api.usage import insights, offers


class Command(BaseCommand):
    help = (
        "Load the catalogue in az/ru/en, the demo subscriber (994516643342), four "
        "test numbers with 30-day usage stories and the admin accounts. Safe to run on every start: what already exists is kept."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete and recreate the demo subscriber and the test numbers",
        )
        parser.add_argument(
            "--refresh",
            action="store_true",
            help="Put the seeded catalogue rows back to their initial content",
        )
        parser.add_argument(
            "--crowd",
            type=int,
            metavar="N",
            help="Also keep N synthetic subscribers with 90 days of usage (the same N gives "
            "the same crowd); 0 removes them",
        )

    def handle(self, *args, **options):
        # Seed data is written in English; the other languages are filled explicitly.
        with translation.override("en"):
            seed_catalogue(refresh=options["refresh"])
            subscriber, created = seed_demo(reset=options["reset"])
            testers = seed_test_numbers(reset=options["reset"])
            crowd = None
            if options["crowd"] is not None:
                crowd = seed_crowd(options["crowd"], reset=options["reset"])
            offers.refresh()
            if crowd and crowd[1]:
                answer_offers()
            insights.refresh()
            detected.refresh_all()
            staff = seed_staff()

        self.stdout.write(self.style.SUCCESS("Catalogue: loaded in az, ru and en"))
        if created:
            self.stdout.write(self.style.SUCCESS(f"Demo subscriber: {subscriber.msisdn} created"))
        else:
            self.stdout.write(f"Demo subscriber: {subscriber.msisdn} kept (--reset recreates it)")
        numbers = ", ".join(tester.msisdn for tester in testers)
        self.stdout.write(self.style.SUCCESS(f"Test numbers (30-day stories): {numbers}"))
        if crowd:
            size, created = crowd
            self.stdout.write(
                self.style.SUCCESS(f"Crowd: {size} synthetic subscribers created")
                if created
                else f"Crowd: {size} synthetic subscribers kept"
            )
        logins = ", ".join(account.msisdn for account in staff)
        self.stdout.write(
            self.style.SUCCESS(f"Admin accounts: {logins} (password: SEED_STAFF_PASSWORD)")
        )
        if settings.DEBUG:
            self.stdout.write(f"Authorization: Bearer {AccessToken.for_user(subscriber)}")
        else:
            self.stdout.write("API token: run `manage.py demo_token` to print one")
