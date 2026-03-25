from django.shortcuts import render, redirect

def index_view(request):
    return redirect("frontend:chat")

def login_view(request):
    return render(request, "auth/login.html")

def register_view(request):
    return render(request, "auth/register.html")

def chat_view(request):
    return render(request, "app/chat.html")
