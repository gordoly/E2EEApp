from django.urls import path

from .views import RegisterView, LoginView, LogoutView, LoginPageView, SignUpPageView

urlpatterns = [
    path('register/', RegisterView.as_view(), name="register"),
    path('login/', LoginView.as_view(), name="login"),
    path('logout/', LogoutView.as_view(), name="logout"),
    path('signin/', LoginPageView.as_view(), name="clientLogin"),
    path('signup/', SignUpPageView.as_view(), name="clientSignup")
]