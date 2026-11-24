from django.urls import path

from . import views

urlpatterns = [
    path('session/start/', views.start_view),
    path('session/answer/', views.answer_view),
    path('session/continue/', views.continue_view),
    path('session/end/', views.end_view),
    path('session/<int:session_id>/', views.session_view),
    path('report/<int:session_id>/', views.report_view),
    path('history/', views.history_view),
]
