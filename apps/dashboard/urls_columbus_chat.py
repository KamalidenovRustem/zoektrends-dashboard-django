"""
Columbus Chat URLs
AI Assistant for Prospect Discovery
"""
from django.urls import path
from apps.dashboard import views_columbus_chat

app_name = 'columbus_chat'

urlpatterns = [
    path('', views_columbus_chat.columbus_chat_index, name='index'),
    path('chat/', views_columbus_chat.chat_message, name='chat'),
    path('reset/', views_columbus_chat.reset_chat, name='reset'),
    path('suggestions/', views_columbus_chat.get_suggestions, name='suggestions'),
    path('insights/', views_columbus_chat.quick_insights, name='insights'),
]
