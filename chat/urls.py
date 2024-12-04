from django.urls import path

from .views import Friends, ChatView

urlpatterns = [
    path('friends/', Friends.as_view(), name="friends"),
    path('chat/<int:room_id>/', ChatView.as_view(), name="home")
]