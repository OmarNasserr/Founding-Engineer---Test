from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from surveys_app.urls import public_urlpatterns, dashboard_urlpatterns

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/auth/', include('accounts_app.urls')),
    path('api/v1/surveys/', include((public_urlpatterns, 'surveys_public'))),
    path('api/v1/dashboard/surveys/', include((dashboard_urlpatterns, 'surveys_dashboard'))),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
