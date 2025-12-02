"""
Jobs URLs
"""
from django.urls import path
from . import views

app_name = 'jobs'

urlpatterns = [
    path('', views.index, name='index'),
    path('api/list/', views.api_list, name='api_list'),
    path('api/filter-options/', views.filter_options, name='filter_options'),
]
