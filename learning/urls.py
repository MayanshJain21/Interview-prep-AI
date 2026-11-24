from django.urls import path

from . import views

urlpatterns = [
    path('profile/', views.profile_view),
    path('mastery/', views.mastery_view),
    path('recommendations/', views.recommendations_view),
    path('analytics/', views.analytics_view),
    path('skills/', views.skills_view),
    path('notes/', views.notes_view),
    path('roadmap/', views.roadmap_view),
    path('roadmap/<int:roadmap_id>/', views.roadmap_detail_view),
    path('roadmap/generate/', views.generate_view),
    path('roadmap/complete/', views.complete_view),
    path('roadmap/reschedule/', views.reschedule_view),
]
