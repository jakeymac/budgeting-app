from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path

from budget import views

urlpatterns = [
    path('', views.home, name='home'),
    path('workspace/', views.home, name='workspace'),
    path('api/budget/', views.budget_api),
    path('api/plans/<str:kind>/', views.plan_api),
    path('api/events/', views.events_api),
    path('api/events/<int:event_id>/', views.events_api),
    path('login/', auth_views.LoginView.as_view(redirect_authenticated_user=True), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('healthz/', views.healthz, name='healthz'),
    path('_deploy/finalize/', views.deploy_finalize, name='deploy-finalize'),
    path('admin/', admin.site.urls),
]
