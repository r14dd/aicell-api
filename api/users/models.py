from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class SubscriberManager(BaseUserManager):
    def create_user(self, msisdn, password=None, **extra):
        user = self.model(msisdn=msisdn, **extra)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, msisdn, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self.create_user(msisdn, password, **extra)


class Subscriber(AbstractBaseUser, PermissionsMixin):
    LINE_TYPES = [("prepaid", "Prepaid"), ("postpaid", "Postpaid")]

    msisdn = models.CharField(max_length=20, unique=True)  # 994XXXXXXXXX
    display_name = models.CharField(max_length=120, blank=True)
    line_type = models.CharField(max_length=10, choices=LINE_TYPES, default="prepaid")
    language = models.CharField(max_length=2, default="en")
    is_premium = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    objects = SubscriberManager()

    USERNAME_FIELD = "msisdn"

    def __str__(self):
        return self.msisdn

    @property
    def display_msisdn(self):
        """994516643342 -> 051 664 33 42"""
        m = self.msisdn
        if len(m) != 12 or not m.startswith("994"):
            return m
        return f"0{m[3:5]} {m[5:8]} {m[8:10]} {m[10:12]}"
