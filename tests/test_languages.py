"""Copy comes back in the language of `Accept-Language`: az or en."""

import re

import pytest
from django.core.management import call_command
from modeltranslation.translator import translator

from .test_docs_conformance import ROWS

AZERBAIJANI = re.compile(r"[əğıöüçşƏĞİÖÜÇŞ]")
READS = [row for row in ROWS if row[0] == "GET" and row[2] != ":todo"]


def get(client, path, language=None):
    headers = {"HTTP_ACCEPT_LANGUAGE": language} if language else {}
    return client.get(path, **headers)


# --- choosing the language --------------------------------------------------


@pytest.mark.parametrize(
    "header,expected",
    [
        (None, "en"),
        ("en", "en"),
        ("az", "az"),
        ("az-AZ,az;q=0.9,en;q=0.8", "az"),
        ("de", "en"),  # unsupported
        ("de-DE,fr;q=0.9", "en"),
        ("fr;q=0.9,az;q=0.8,en;q=0.7", "az"),  # the best supported one
        ("*", "en"),
        ("not a language", "en"),
    ],
)
def test_language_comes_from_the_header(client, header, expected):
    response = get(client, "/api/sim/", header)
    assert response.status_code == 200
    assert response["Content-Language"] == expected
    assert "Accept-Language" in response["Vary"]


def test_a_cookie_does_not_change_the_language(client):
    client.cookies["django_language"] = "az"
    assert get(client, "/api/sim/")["Content-Language"] == "en"
    assert get(client, "/api/sim/", "az")["Content-Language"] == "az"


@pytest.mark.parametrize("language", ["az", "en"])
@pytest.mark.parametrize("method,path,status", READS)
def test_every_read_answers_in_every_language(client, method, path, status, language):
    response = get(client, path, language)
    assert response.status_code == 200
    assert response["Content-Language"] == language


# --- what is translated -----------------------------------------------------


def test_fixed_screen_copy_is_translated(client):
    en = get(client, "/api/sim/").json()
    az = get(client, "/api/sim/", "az").json()
    assert en["rows"][0]["label"] == "Line settings"
    assert az["rows"][0]["label"] == "Xətt ayarları"
    assert az["badge"] == "4G (LTE) aktivdir"
    # values that are not copy stay the same
    assert en["details"][0]["value"] == az["details"][0]["value"]


def test_catalogue_content_is_translated(client):
    path = "/api/tariffs/catalogue/digimax/?plan=digimax-10"
    en, az = (get(client, path, language).json() for language in ("en", "az"))
    assert en["plans"][0]["features"][0] == {
        "kind": "internet",
        "label": "Internet",
        "value": "5 GB",
    }
    assert az["plans"][0]["features"][0] == {
        "kind": "internet",
        "label": "İnternet",
        "value": "5 GB",
    }
    assert az["cta"] == "18.00 ₼-a abunə ol"
    # ids, prices and brand names are not translated
    assert en["id"] == az["id"] == "digimax"
    assert en["name"] == az["name"] == "DigiMax"
    assert [plan["price"] for plan in en["plans"]] == [plan["price"] for plan in az["plans"]]


@pytest.mark.parametrize(
    "path",
    [
        "/api/packs/internet/",
        "/api/packs/social/tehsil/",
        "/api/packs/roaming/",
        "/api/kredit/",
        "/api/kredit/tamamla/",
        "/api/sim/services/",
        "/api/sim/services/missed-call/",
        "/api/sim/puk/",
        "/api/sim/esim/",
        "/api/content/home/",
        "/api/content/stories/especially/",
        "/api/content/lottery/rules/",
        "/api/content/notifications/",
        "/api/content/offers/apps/",
        "/api/referral/me/",
        "/api/tariffs/my/",
        "/api/tariffs/my/usage/",
        "/api/tariffs/change/",
        "/api/tariffs/premium/",
        "/api/billing/top-up/methods/",
        "/api/assistant/inbox/",
    ],
)
def test_screens_read_in_azerbaijani(client, path):
    en = get(client, path, "en").content.decode()
    az = get(client, path, "az").content.decode()
    assert AZERBAIJANI.search(az)
    assert en != az


def test_dates_are_named_in_the_language(client):
    path = "/api/tariffs/my/usage/"
    assert get(client, path, "en").json()["renewal_label"] == "Renews 25 October, 08:00"
    assert get(client, path, "az").json()["renewal_label"] == "25 Oktyabr, 08:00-da yenilənir"


# --- messages ---------------------------------------------------------------


@pytest.mark.parametrize(
    "language,detail",
    [
        ("en", "Voucher redemption is not part of this prototype yet"),
        ("az", "Vauçerin istifadəsi hələ bu prototipdə yoxdur"),
    ],
)
def test_todo_notice(client, language, detail):
    response = client.post_json("/api/billing/top-up/voucher/", HTTP_ACCEPT_LANGUAGE=language)
    assert response.json() == {"code": "not_implemented", "detail": detail}


@pytest.mark.parametrize(
    "language,detail",
    [
        ("en", "SimTaksit 2.00 ₼ will be added to your balance (prototype)"),
        ("az", "SimTaksit 2.00 ₼ balansınıza əlavə olunacaq (prototip)"),
    ],
)
def test_todo_notice_with_values(client, language, detail):
    response = client.post_json(
        "/api/kredit/products/simtaksit/take/", {"amount": "2.00"}, HTTP_ACCEPT_LANGUAGE=language
    )
    assert response.json()["detail"] == detail


@pytest.mark.parametrize(
    "language,required,amount",
    [
        ("en", "This field is required.", "Enter an amount between 1.00 and 500.00 ₼"),
        ("az", "Bu sahə tələb edilir.", "1.00 ilə 500.00 ₼ arasında məbləğ daxil edin"),
    ],
)
def test_validation_errors(client, language, required, amount):
    """Both the framework's own messages and ours are in the requested language."""
    import uuid

    headers = {"HTTP_ACCEPT_LANGUAGE": language, "HTTP_IDEMPOTENCY_KEY": str(uuid.uuid4())}
    missing = client.post_json("/api/billing/top-up/card/", {}, **headers).json()
    assert missing["code"] == "validation_error"
    assert missing["errors"]["card_bin"] == [required]
    assert missing["detail"] == required

    out_of_range = client.post_json(
        "/api/billing/top-up/card/", {"card_bin": "416300", "amount": "0.10"}, **headers
    ).json()
    assert out_of_range["detail"] == amount


@pytest.mark.parametrize(
    "language,detail",
    [
        ("en", "Not enough balance for this pack"),
        ("az", "Bu paket üçün balans kifayət etmir"),
    ],
)
def test_business_errors(client, language, detail):
    response = client.post_json(
        "/api/packs/internet/purchase/",
        {"pack_id": "hv-100gb"},
        HTTP_ACCEPT_LANGUAGE=language,
        HTTP_IDEMPOTENCY_KEY="5f0c2b9e-7a54-4c2b-9d0e-1f3a5b7c9d11",
    )
    assert response.status_code == 402
    assert response.json() == {"code": "insufficient_balance", "detail": detail}


@pytest.mark.parametrize(
    "language,message",
    [
        ("en", "Thanks! Your rating helps us a lot"),
        ("az", "Təşəkkürlər! Qiymətiniz bizə çox kömək edir"),
    ],
)
def test_success_messages(client, language, message):
    response = client.post_json(
        "/api/content/app-rating/", {"stars": 5}, HTTP_ACCEPT_LANGUAGE=language
    )
    assert response.json() == {"message": message}


@pytest.mark.parametrize(
    "language,unauthenticated,missing",
    [
        ("en", "Authentication required", "Not found."),
        ("az", "Avtorizasiya tələb olunur", "Tapılmadı."),
    ],
)
def test_401_and_404(anon, client, language, unauthenticated, missing):
    assert get(anon, "/api/users/me/", language).json()["detail"] == unauthenticated
    assert get(client, "/api/packs/social/nope/", language).json()["detail"] == missing
    assert get(client, "/api/nope/", language).json()["detail"] == missing


def test_error_codes_never_change_with_the_language(client):
    """Clients branch on `code`; only `detail` is for people."""
    codes = {
        get(client, "/api/packs/social/nope/", language).json()["code"] for language in ("en", "az")
    }
    assert codes == {"not_found"}


def test_a_receipt_is_written_in_the_language_of_the_purchase(client):
    import uuid

    response = client.post_json(
        "/api/packs/internet/purchase/",
        {"pack_id": "unlimited-1h"},
        HTTP_ACCEPT_LANGUAGE="az",
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    ).json()
    assert response["activation"]["label"] == "Limitsiz 1 saat"
    assert response["transaction"]["title"] == "Limitsiz 1 saat paketi"
    # ... and stays that way when the history is read in another language
    newest = get(client, "/api/billing/transactions/", "en").json()["results"][0]
    assert newest["title"] == "Limitsiz 1 saat paketi"


# --- completeness -----------------------------------------------------------


def test_every_code_string_is_translated(db):
    """Fails when a `_()` string is missing from a .po file or has no translation."""
    call_command("sync_locale", "--check")


def test_compiled_catalogues_match_their_sources():
    """The .mo files in the repository are the ones the .po files produce."""
    import polib
    from django.conf import settings

    for language in ("az",):
        folder = settings.LOCALE_PATHS[0] / language / "LC_MESSAGES"
        source = {entry.msgid: entry.msgstr for entry in polib.pofile(str(folder / "django.po"))}
        compiled = {entry.msgid: entry.msgstr for entry in polib.mofile(str(folder / "django.mo"))}
        assert source == compiled, f"run `manage.py sync_locale` ({language})"


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def test_no_seeded_text_is_left_untranslated(subscriber):
    """Every translated field that has English text also has Azerbaijani."""
    checked = 0
    for model in translator.get_registered_models():
        fields = translator.get_options_for_model(model).get_field_names()
        for row in model.objects.all():
            for field in fields:
                english = getattr(row, f"{field}_en")
                if not english:
                    continue
                for language in ("az",):
                    value = getattr(row, f"{field}_{language}")
                    assert value, f"{model.__name__}.{field}_{language} is empty (id {row.pk})"
                    assert all(_strings(value)) or not any(_strings(english))
                    checked += 1
    assert checked > 150


def test_catalogue_cache_keeps_languages_apart(client):
    """The second read of each language comes from the cache and must not mix them up."""
    path = "/api/packs/roaming/"
    first = {language: get(client, path, language).json() for language in ("en", "az")}
    again = {language: get(client, path, language).json() for language in ("en", "az")}
    assert first == again
    assert first["en"]["results"][1]["sub"] == "10 days"
    assert first["az"]["results"][1]["sub"] == "10 gün"
