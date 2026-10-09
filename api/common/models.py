from django.db import models


class CatalogueItem(models.Model):
    """Base of everything editors manage in the admin: ordered and switchable."""

    order = models.PositiveSmallIntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True
        ordering = ["order", "id"]


class ActiveQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)
