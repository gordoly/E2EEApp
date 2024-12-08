from rest_framework.views import APIView
from rest_framework.response import Response
from django.views import View
from django.shortcuts import render, redirect

from .serialiser import UserSerialiser
from .models import AccountUser

class RegisterView(APIView):
    def post(self, request):
        serialiser = UserSerialiser(data=request.data)
        
        if not serialiser.is_valid():
            return Response({'message': serialiser.errors}, status=400)
        
        serialiser.save()
        request.session["username"] = request.data['username']

        return Response({'message': "/auth/signin/"}, status=200)

class LoginView(APIView):
    def post(self, request):
        username = request.data['username']
        password = request.data['password']

        try:
            user = AccountUser.objects.get(username=username)
            if not user.check_password(password):
                return Response({'message': 'Account credentials could not be found'}, status=403)
            request.session["username"] = username

            return Response({'message': "/friends/"}, status=200)
        
        except AccountUser.DoesNotExist:
            return Response({'message': 'Account credentials could not be found'}, status=403)
        
class VerifyPassword(APIView):
    def post(self, request):
        if "username" in request.session:
            username = request.session["username"]
            password = request.data["password"]

            user = AccountUser.objects.get(username=username)
            if not user.check_password(password):
                return Response({'message': 'Password invalid'}, status=403)
            
            request.session["username"] = username

            return Response({'message': 'Password valid'}, status=200)
        
        return Response({'message': 'Password invalid'}, status=403)

class LogoutView(APIView):
    def get(self, request):
        request.session.flush() 
        return redirect("/auth/signin/")
    
class LoginPageView(View):
    def get(self, request):
        return render(request, "login.html", {})
    
class SignUpPageView(View):
    def get(self, request):
        return render(request, "signup.html", {})