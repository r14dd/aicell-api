"""One-click sign-in to the admin as a seeded staff account, for demos.

Off unless `DEMO_ADMIN_LOGIN` is on. While it is on, anyone who can open the
admin login page can enter as any of the seeded accounts, the superadmin
included, without a password.
"""

from django.conf import settings
from django.contrib.auth import login
from django.http import Http404
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from api.seeding.staff import ACCOUNTS
from api.users.models import Subscriber

BACKEND = "django.contrib.auth.backends.ModelBackend"


def accounts() -> list[dict]:
    return [{"login": key, "name": name} for key, (name, _group) in ACCOUNTS.items()]


def context(request):
    """Template context: the buttons on the admin login page, when the switch is on."""
    return {"demo_logins": accounts() if settings.DEMO_ADMIN_LOGIN else []}


@require_POST
def demo_login(request, account):
    if not settings.DEMO_ADMIN_LOGIN or account not in ACCOUNTS:
        raise Http404
    user = Subscriber.objects.filter(msisdn=account, is_staff=True, is_active=True).first()
    if user is None:
        raise Http404  # not seeded yet
    login(request, user, backend=BACKEND)
    target = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(target, {request.get_host()}, request.is_secure()):
        target = ""
    return redirect(target or "admin:index")
