"""
Authentication URLs
"""
from django.urls import path
from django.shortcuts import redirect
from . import views

urlpatterns = [
    path('', lambda request: redirect('companies:index'), name='home'),
    path('login/', views.show_login, name='login_page'),
    path('login/authenticate/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
]
