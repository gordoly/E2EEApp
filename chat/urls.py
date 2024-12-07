from django.urls import path

from .views import Friends, ChatView, ChatHistoryView, SavePublicKeyView, RoomMembersView, RedirectView

urlpatterns = [
    path('friends/', Friends.as_view(), name="friends"),
    path('chat/<int:room_id>/', ChatView.as_view(), name="home"),
    path('history/', ChatHistoryView.as_view(), name="history"),
    path('key/save/', SavePublicKeyView.as_view(), name="key"),
    path('members/<int:room_id>/', RoomMembersView.as_view(), name="home"),
    path('', RedirectView.as_view(), name="redirect")
]