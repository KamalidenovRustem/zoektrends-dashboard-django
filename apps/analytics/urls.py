"""
Analytics URLs
"""
from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    path('chat/', views.chat, name='chat'),
]
