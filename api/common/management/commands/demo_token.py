from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from rest_framework_simplejwt.tokens import AccessToken

from api.users.models import Subscriber


class Command(BaseCommand):
    help = "Print an access token for a subscriber (the demo one by default)."

    def add_arguments(self, parser):
        parser.add_argument("msisdn", nargs="?", default=settings.DEMO_MSISDN)

    def handle(self, *args, **options):
        subscriber = Subscriber.objects.filter(msisdn=options["msisdn"]).first()
        if subscriber is None:
            raise CommandError(f"No subscriber {options['msisdn']}; run `manage.py seed` first")
        self.stdout.write(str(AccessToken.for_user(subscriber)))
