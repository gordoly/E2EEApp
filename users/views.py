from rest_framework.views import APIView
from rest_framework.response import Response
from django.views import View
from django.shortcuts import render, redirect

from .serialiser import UserSerialiser
from .models import AccountUser

class RegisterView(APIView):
    def post(self, request):
        """
        Post request handler for RegisterView.

        Intended to create a new user account when a user signs up and submits their details.

        Args:
            request (Request): The request object from the POST request.
        
        Returns:
            Response: A response object with a message that details errors in the input
            provided, such as missing data, or a message with a link that the page should direct
            the user to if the registration is successful.
        """
        serialiser = UserSerialiser(data=request.data)
        
        if not serialiser.is_valid():
            return Response({'message': serialiser.errors}, status=400)
        
        serialiser.save()
        request.session["username"] = request.data['username']

        return Response({'message': "/auth/signin/"}, status=200)

class LoginView(APIView):
    def post(self, request):
        """
        Post request handler for LoginView.

        Intended to authenticate a user when they submit their login credentials upon login.

        Args:
            request (Request): The request object from the POST request.

        Returns:
            Response: A response object with an error message if the credentials do not match
            some record in the database or a link that the page should direct the user too if 
            the login is successful.
        """
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
        """
        Post request handler for VerifyPassword.

        Intended to verify a user's password when they submit their password upon login. Does not
        use the client's username from request object but rather from the username is stored in the
        session. Used to verify the password that the user has provided the correct password to be
        used for derviving a PBKDF2 key used for encrypting and decrypting data stored in the client's
        IndexDB database on the browser.

        Args:
            request (Request): The request object from the POST request.

        Returns:
            Response: A response object with a message that details if the password is valid or not.
        """
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
        """
        Get request handler for LogoutView.
        
        Intended to log out a user by clearing the session data.

        Args:
            request (Request): The request object from the GET request.

        Returns:
            Response: A response object that redirects the user to the login page.
        """
        request.session.flush() 
        return redirect("/auth/signin/")
    
class LoginPageView(View):
    def get(self, request):
        """
        Get request handler for LoginPageView.

        Intended to render the login page.

        Args:
            request (Request): The request object from the GET request.
        
        Returns:
            Response: A response object that renders the login
        """
        return render(request, "login.html", {})
    
class SignUpPageView(View):
    def get(self, request):
        """
        Get request handler for SignUpPageView.

        Intended to render the sign up page.

        Args:
            request (Request): The request object from the GET request.

        Returns:
            Response: A response object that renders the sign up page.
        """
        return render(request, "signup.html", {})