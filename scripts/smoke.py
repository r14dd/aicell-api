#!/usr/bin/env python3
"""Check a running deployment from the outside.

    python scripts/smoke.py http://localhost:8010 --token "$(docker compose exec -T web python manage.py demo_token)"

Calls every endpoint of docs/api/*.md in az, ru and en, then signs in to the
admin panel as each seeded role. Uses only the standard library, so it runs
anywhere Python does. Exits non-zero when anything is off.
"""

import argparse
import http.cookiejar
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs" / "api"
ROW = re.compile(r"^\| (GET|POST|PATCH|DELETE) \| `([^`]*)`[^|]*\| `([^`]+)` \|")
LANGUAGES = ("az", "ru", "en")

PARAMS = {
    "billing": {"<id>": "1"},
    "tariffs": {"<family>": "digimax"},
    "packs": {"<slug>": "tehsil"},
    "kredit": {"<slug>": "simtaksit"},
    "sim": {"<slug>": "missed-call"},
    "content": {"<key>": "especially", "<id>": "wingz", "<slug>": "ninja-saga-2"},
    "assistant": {"<id>": "3513323"},
    "usage": {"<id>": "9001"},
    "insights": {"<id>": "7001"},
}
# Bodies of the implemented writes; everything else is sent `{}`.
BODIES = {
    "/api/billing/top-up/card/": {"card_bin": "416300", "amount": "1.00"},
    "/api/billing/top-up/akart/": {"akart_msisdn": "994516643342", "amount": "1.00"},
    "/api/billing/top-up/google-pay/": {"amount": "1.00", "payment_token": "simulated"},
    "/api/billing/steam/top-up/": {"account": "gamer_01", "amount": "1.00"},
    "/api/packs/internet/purchase/": {"pack_id": "daily-500mb"},
    "/api/packs/social/tehsil/activate/": {"plan_id": "10gb"},
    "/api/packs/roaming/purchase/": {"pack_id": "r-500mb"},
    "/api/sim/line/": {"mobile_internet": True},
    "/api/sim/call-forwarding/": {"busy": False},
    "/api/sim/roaming/": {"enabled": False},
    "/api/sim/sms/": {"language": "az"},
    "/api/sim/services/missed-call/subscribe/": {"options": []},
    "/api/content/app-rating/": {"stars": 5},
    "/api/assistant/conversations/": {"source": "smoke"},
    "/api/assistant/conversations/3513323/messages/": {"content": "balans"},
    "/api/assistant/conversations/3513323/rate/": {"stars": 5},
}
PUBLIC = ("/api/users/otp/", "/api/users/token/refresh/")
ROLES = {
    # login: (a page the role may open, a page it may not)
    "superadmin": ("/admin/billing/transaction/", None),
    "content": ("/admin/tariffs/tariffplan/", "/admin/billing/transaction/"),
    "support": ("/admin/users/subscriber/", "/admin/tariffs/tariffplan/"),
    "finance": ("/admin/billing/transaction/", "/admin/users/subscriber/"),
}


def documented_rows():
    for page in sorted(DOCS.glob("*.md")):
        for line in page.read_text().splitlines():
            match = ROW.match(line)
            if not match:
                continue
            method, path, status = match.groups()
            path, _, query = path.partition("?")
            path = path.lstrip("/")  # a domain's root is written `/`
            for placeholder, value in PARAMS.get(page.stem, {}).items():
                path = path.replace(placeholder, value)
            if path == "offers/apps/wingz/subscribe/":
                path = "offers/apps/kinon/subscribe/"
            search = (
                "?q=test"
                if status == ":todo" and page.stem == "content" and query.startswith("q=")
                else ""
            )
            yield method, f"/api/{page.stem}/{path}{search}", status


class Api:
    def __init__(self, base, token):
        self.base, self.token, self.throttled = base.rstrip("/"), token, 0

    def call(self, method, path, language, body=None):
        headers = {
            "Accept": "application/json",
            "Accept-Language": language,
            "Content-Type": "application/json",
            "Idempotency-Key": str(uuid.uuid4()),
        }
        if self.token and not path.startswith(PUBLIC):
            headers["Authorization"] = f"Bearer {self.token}"
        data = None if method == "GET" else json.dumps(body or {}).encode()
        for _attempt in range(4):
            request = urllib.request.Request(
                self.base + path, data=data, method=method, headers=headers
            )
            try:
                with urllib.request.urlopen(request, timeout=20) as response:
                    return response.status, response.headers, response.read()
            except urllib.error.HTTPError as error:
                # Sign-in is limited on purpose; for the rest, wait as the server asks.
                if error.code == 429 and not path.startswith(PUBLIC):
                    self.throttled += 1
                    time.sleep(int(error.headers.get("Retry-After", "5")) + 1)
                    continue
                return error.code, error.headers, error.read()
        return 429, {}, b""


def check_api(api):
    problems, counts, notices = [], {}, {}
    for method, path, status in documented_rows():
        for language in LANGUAGES:
            code, headers, raw = api.call(method, path, language, BODIES.get(path.split("?")[0]))
            counts[code] = counts.get(code, 0) + 1
            where = f"{method} {path} [{language}]"
            if code >= 500 and code != 501:
                problems.append(f"{where}: {code}")
                continue
            if code == 429:
                if not path.startswith(PUBLIC):
                    problems.append(f"{where}: still throttled")
                continue
            if headers.get("Content-Language") != language:
                problems.append(f"{where}: Content-Language is {headers.get('Content-Language')}")
            try:
                body = json.loads(raw)
            except ValueError:
                problems.append(f"{where}: body is not JSON")
                continue
            if status == ":todo":
                if code != 501 or body.get("code") != "not_implemented":
                    problems.append(f"{where}: expected 501, got {code}")
                notices.setdefault((method, path), []).append(body.get("detail"))
            elif method == "GET" and code != 200:
                problems.append(f"{where}: expected 200, got {code}")
            elif code not in (200, 201, 402, 409):
                problems.append(f"{where}: unexpected {code} {body}")
    for (method, path), texts in notices.items():
        # Compared among the answers received: a throttled sign-in call has no notice.
        if len(set(texts)) != len(texts):
            problems.append(f"{method} {path}: the 501 notice is the same in two languages")
    return problems, counts


def check_health(api):
    problems = []
    for path in ("/api/health/", "/api/health/ready/"):
        code, _headers, raw = api.call("GET", path, "en")
        if code != 200:
            problems.append(f"{path}: {code} {raw[:200]!r}")
        else:
            print(f"  {path} -> {json.loads(raw)}")
    return problems


def check_auth(api):
    """Without a token a protected endpoint answers 401, unless DEMO_AUTH is on."""
    anonymous = Api(api.base, token=None)
    code, _headers, raw = anonymous.call("GET", "/api/users/me/", "en")
    if code == 200:
        print("  note: DEMO_AUTH is on, requests without a token act as the demo subscriber")
        return []
    print("  without a token: 401")
    return [] if code == 401 else [f"/api/users/me/ without a token: {code} {raw[:120]!r}"]


def check_admin(base, password):
    problems = []
    for login, (allowed, forbidden) in ROLES.items():
        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        login_url = f"{base}/admin/login/?next=/admin/"
        opener.open(login_url, timeout=20).read()
        csrf = next(cookie.value for cookie in jar if cookie.name == "csrftoken")
        form = urllib.parse.urlencode(
            {
                "username": login,
                "password": password,
                "csrfmiddlewaretoken": csrf,
                "next": "/admin/",
            }
        ).encode()
        request = urllib.request.Request(login_url, data=form, headers={"Referer": login_url})
        page = opener.open(request, timeout=20)
        if not page.url.rstrip("/").endswith("/admin"):
            problems.append(f"admin: {login} could not sign in")
            continue

        def status(path, opener=opener):
            try:
                return opener.open(base + path, timeout=20).status
            except urllib.error.HTTPError as error:
                return error.code

        results = {"dashboard": status("/admin/"), "allowed": status(allowed)}
        if forbidden:
            results["forbidden"] = status(forbidden)
        expected = {"dashboard": 200, "allowed": 200, **({"forbidden": 403} if forbidden else {})}
        print(f"  {login:<11} {results}")
        if results != expected:
            problems.append(f"admin: {login} got {results}, expected {expected}")
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("base", help="e.g. http://localhost:8010")
    parser.add_argument("--token", required=True, help="access token of the demo subscriber")
    parser.add_argument("--staff-password", default="aicell-demo")
    args = parser.parse_args()
    api = Api(args.base, args.token)

    print("health")
    problems = check_health(api)
    print("api: every documented endpoint in az, ru and en")
    api_problems, counts = check_api(api)
    problems += api_problems + check_auth(api)
    total = sum(counts.values())
    print(
        f"  {total} calls, by status: {dict(sorted(counts.items()))}; waited on a 429 {api.throttled} times"
    )
    print("admin: sign in as each role")
    problems += check_admin(api.base, args.staff_password)

    if problems:
        print(f"\n{len(problems)} problem(s):")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("\nAll good.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
