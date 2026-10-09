from django.apps import AppConfig


class CommonConfig(AppConfig):
    """Shared building blocks; an app only so it can hold management commands."""

    name = "api.common"
    label = "common"
