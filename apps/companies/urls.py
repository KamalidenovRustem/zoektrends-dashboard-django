"""
Companies URLs
"""
from django.urls import path
from . import views

app_name = 'companies'

urlpatterns = [
    path('', views.index, name='index'),
    path('contact-details/', views.get_contact_details, name='contact_details'),
    path('update/', views.update_company, name='update_company'),
]
