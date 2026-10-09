from django.core.management.base import BaseCommand

from api.insights import services


class Command(BaseCommand):
    help = (
        "Run the insight detectors for every subscriber, as the nightly task does. "
        "Open insights get fresh figures; new ones are written unless their kind is snoozed."
    )

    def handle(self, *args, **options):
        kept = services.refresh_all()
        self.stdout.write(self.style.SUCCESS(f"Insights open after the run: {kept}"))
