from django.urls import path

from . import views

urlpatterns = [
    path("inbox/", views.inbox_view),
    path("conversations/", views.conversations_view),
    path("conversations/<int:id>/messages/", views.messages_view),
    path("conversations/<int:id>/voice/", views.voice_view),
    path("conversations/<int:id>/rate/", views.rate_view),
    path("feedback/", views.feedback_view),
]
