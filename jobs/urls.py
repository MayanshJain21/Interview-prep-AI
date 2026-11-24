from django.urls import path

from . import views

urlpatterns = [
    path('create/', views.create_job),
    path('analyze/', views.analyze_job),
    path('history/', views.history),
    path('analysis/<int:analysis_id>/', views.analysis_detail),
    path('<int:job_id>/', views.job_detail),
]
