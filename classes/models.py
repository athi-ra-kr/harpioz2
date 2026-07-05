import uuid
import random
import string
from django.db import models
from django.utils import timezone


def generate_class_id():
    """Generate a short readable class ID like 'rty67888'"""
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choices(chars, k=8))


def generate_password():
    """Generate a 6-digit numeric password"""
    return ''.join(random.choices(string.digits, k=6))


class LiveClass(models.Model):
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('live', 'Live'),
        ('ended', 'Ended'),
    ]

    class_id = models.CharField(max_length=12, unique=True, default=generate_class_id)
    title = models.CharField(max_length=200)
    password = models.CharField(max_length=10, default=generate_password)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    scheduled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    stream_key = models.CharField(max_length=64, unique=True, blank=True)
    chat_enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.class_id})"

    def save(self, *args, **kwargs):
        if not self.stream_key:
            self.stream_key = f"class-{self.class_id}"
        super().save(*args, **kwargs)

    def get_join_url(self, request=None):
        path = f"/class/{self.class_id}/"
        if request:
            return request.build_absolute_uri(path)
        return path


class Participant(models.Model):
    live_class = models.ForeignKey(LiveClass, on_delete=models.CASCADE, related_name='participants')
    name = models.CharField(max_length=100)
    email = models.EmailField()
    mobile = models.CharField(max_length=20)
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)
    session_key = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ['-joined_at']

    def __str__(self):
        return f"{self.name} in {self.live_class.title}"


class ChatMessage(models.Model):
    live_class = models.ForeignKey(LiveClass, on_delete=models.CASCADE, related_name='messages')
    participant_name = models.CharField(max_length=100)
    is_admin = models.BooleanField(default=False)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        ordering = ['created_at']


class SiteSettings(models.Model):
    """Singleton model — only one row ever exists."""
    site_title = models.CharField(max_length=100, default='Harpioz')
    site_description = models.TextField(default='Private live education platform')
    logo = models.ImageField(upload_to='settings/', blank=True, null=True)
    favicon = models.ImageField(upload_to='settings/', blank=True, null=True)
    privacy_policy = models.TextField(blank=True, default='')
    terms = models.TextField(blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Site Settings'

    def __str__(self):
        return 'Site Settings'

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
