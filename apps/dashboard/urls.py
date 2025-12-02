"""
Dashboard URLs
"""
from django.urls import path
from . import views
from . import views_ai_research

app_name = 'dashboard'

urlpatterns = [
    path('', views.index, name='index'),
    path('stats/', views.get_stats, name='stats'),
    path('analytics/', views.analytics, name='analytics'),
    path('api/', views.api_management, name='api'),
    path('api/test-connection/', views.test_connection, name='test_connection'),
    path('api/company-jobs/', views.get_company_jobs, name='company_jobs'),
    path('api/analytics-chat/', views.analytics_chat, name='analytics_chat'),
    path('companies/contact-details/', views.get_contact_details, name='contact_details'),
    path('companies/research-streaming/', views_ai_research.research_company_streaming, name='research_streaming'),
    path('skills-registry/', views.skills_registry, name='skills_registry'),
    path('skills-registry/list/', views.skills_registry_list, name='skills_registry_list'),
    path('skills-registry/save/', views.skills_registry_save, name='skills_registry_save'),
    path('skills-registry/toggle-active/', views.skills_registry_toggle_active, name='skills_registry_toggle_active'),
    path('skills-registry/delete/', views.skills_registry_delete, name='skills_registry_delete'),
    path('configuration/', views.configuration, name='configuration'),
    path('configuration/list/', views.configuration_list, name='configuration_list'),
    path('configuration/save/', views.configuration_save, name='configuration_save'),
    path('configuration/activate/', views.configuration_activate, name='configuration_activate'),
    path('configuration/deactivate/', views.configuration_deactivate, name='configuration_deactivate'),
    path('configuration/delete/', views.configuration_delete, name='configuration_delete'),
]
