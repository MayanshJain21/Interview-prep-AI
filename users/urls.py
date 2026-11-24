from django.urls import path
from . import views

urlpatterns = [
    path('signup/', views.signup, name='signup'),
    path('login/', views.login, name='login'),
    path('google/', views.google_login, name='google_login'),
    path('google/config/', views.google_config, name='google_config'),
    path('me/', views.me, name='me'),
]
