"""
Configuration URLs
"""
from django.urls import path
from apps.dashboard import views

app_name = 'configuration'

urlpatterns = [
    path('', views.configuration, name='index'),
    path('list/', views.configuration_list, name='list'),
    path('save/', views.configuration_save, name='save'),
    path('activate/', views.configuration_activate, name='activate'),
    path('deactivate/', views.configuration_deactivate, name='deactivate'),
    path('delete/', views.configuration_delete, name='delete'),
]
