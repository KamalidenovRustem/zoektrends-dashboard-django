"""
Main URL Configuration for ZoekTrends Dashboard
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Authentication
    path('', include('apps.authentication.urls')),
    
    # Dashboard
    path('dashboard/', include('apps.dashboard.urls')),
    
    # Jobs
    path('dashboard/jobs/', include('apps.jobs.urls')),
    
    # Companies
    path('dashboard/companies/', include('apps.companies.urls')),
    
    # Analytics (AI Chat)
    path('dashboard/analytics/', include('apps.analytics.urls')),
    
    # Configuration
    path('dashboard/configuration/', include('apps.configuration.urls')),
    
    # Columbus Chat (AI Assistant)
    path('dashboard/columbus/', include('apps.dashboard.urls_columbus_chat')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Customize admin site
admin.site.site_header = "ZoekTrends Dashboard Administration"
admin.site.site_title = "ZoekTrends Admin"
admin.site.index_title = "Welcome to ZoekTrends Dashboard"
