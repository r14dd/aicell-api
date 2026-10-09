"""Keep `locale/*/LC_MESSAGES/django.po` in step with the code and compile them.

Does the job of `makemessages` + `compilemessages` without GNU gettext: it
reads the literal passed to every `_()`, `gettext()` and `gettext_lazy()` call
under `api/`, adds new ones to each `.po` (untranslated), drops the ones no
longer used and writes the `.mo` files.
"""

import ast
from pathlib import Path

import polib
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

CALLS = {"_", "gettext", "gettext_lazy"}
LANGUAGES = ("az", "ru")


def source_messages(root: Path) -> dict[str, list[str]]:
    """Every translatable literal under `root`, with the files that use it."""
    found: dict[str, list[str]] = {}
    for path in sorted(root.rglob("*.py")):
        if "migrations" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in CALLS
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                location = str(path.relative_to(root.parent))
                found.setdefault(node.args[0].value, [])
                if location not in found[node.args[0].value]:
                    found[node.args[0].value].append(location)
    return found


def po_path(language: str) -> Path:
    return Path(settings.LOCALE_PATHS[0]) / language / "LC_MESSAGES" / "django.po"


def load(language: str) -> polib.POFile:
    path = po_path(language)
    if path.exists():
        return polib.pofile(str(path))
    po = polib.POFile()
    po.metadata = {
        "Project-Id-Version": "aicell-api",
        "Language": language,
        "MIME-Version": "1.0",
        "Content-Type": "text/plain; charset=UTF-8",
        "Content-Transfer-Encoding": "8bit",
    }
    return po


class Command(BaseCommand):
    help = "Update the az/ru .po files from the code and compile the .mo files."

    def add_arguments(self, parser):
        parser.add_argument(
            "--check",
            action="store_true",
            help="Change nothing; fail if a message is missing, untranslated or stale",
        )

    def handle(self, *args, **options):
        messages = source_messages(Path(settings.BASE_DIR) / "api")
        problems = []
        for language in LANGUAGES:
            po = load(language)
            known = {entry.msgid: entry for entry in po}
            missing = [msgid for msgid in messages if msgid not in known]
            stale = [msgid for msgid in known if msgid not in messages]
            empty = [entry.msgid for entry in po if entry.msgid in messages and not entry.msgstr]

            if options["check"]:
                problems += [f"{language}: not in .po: {msgid!r}" for msgid in missing]
                problems += [f"{language}: no longer used: {msgid!r}" for msgid in stale]
                problems += [f"{language}: untranslated: {msgid!r}" for msgid in empty]
                continue

            for msgid in missing:
                po.append(polib.POEntry(msgid=msgid, msgstr=""))
            for msgid in stale:
                po.remove(known[msgid])
            for entry in po:
                entry.occurrences = [(location, "") for location in messages[entry.msgid]]
            po.sort(key=lambda entry: (entry.occurrences[0][0], entry.msgid))
            path = po_path(language)
            path.parent.mkdir(parents=True, exist_ok=True)
            po.save(str(path))
            po.save_as_mofile(str(path.with_suffix(".mo")))
            self.stdout.write(
                f"{language}: {len(po)} messages, {len(missing)} added, "
                f"{len(stale)} removed, {len(empty) + len(missing)} untranslated"
            )

        if problems:
            raise CommandError("\n".join(problems))
        if options["check"]:
            self.stdout.write(self.style.SUCCESS(f"{len(messages)} messages, all translated"))
