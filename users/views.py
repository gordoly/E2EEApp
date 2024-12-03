from rest_framework.views import APIView
from rest_framework.response import Response
from django.http import HttpResponseRedirect
from django.views import View
from django.shortcuts import render

from .serialiser import UserSerialiser
from .models import AccountUser

class RegisterView(APIView):
    def post(self, request):
        serialiser = UserSerialiser(data=request.data)
        if not serialiser.is_valid():
            return Response({'message': serialiser.errors}, status=400)
        serialiser.save()
        return HttpResponseRedirect("/auth/signin/")

class LoginView(APIView):
    def post(self, request):
        username = request.data['username']
        password = request.data['password']

        try:
            user = AccountUser.objects.get(username=username)
            if not user.check_password(password):
                raise Response({'message': 'Account credentials could not be found'}, status=403)
            request.session["username"] = username

            return HttpResponseRedirect("/friends/")
        
        except AccountUser.DoesNotExist:
            return Response({'message': 'Account credentials could not be found'}, status=403)

class LogoutView(APIView):
    def post(self, request):
        request.session["username"] = ""
        return HttpResponseRedirect("/auth/signin/")