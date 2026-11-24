from django.urls import path

from . import views

urlpatterns = [
    path('languages/', views.language_list),
    path('companies/', views.company_list),
    path('session/start/', views.start_session),
    path('session/active/', views.active_session),
    path('session/finish/', views.finish_session),
    path('session/<int:session_id>/', views.session_detail),
    path('run/', views.run_code),
    path('submit/', views.submit_code),
    path('hint/', views.get_hint),
]
