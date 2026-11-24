from django.urls import path
from . import views, hr_interview

urlpatterns = [
    path('mcq/generate/', views.generate_mcqs, name='generate_mcqs'),
    path('mcq/filter-skills/', views.filter_skills, name='filter_skills'),
    path('mcq/submit/', views.submit_mcqs, name='submit_mcqs'),
    path('ats/check/', views.check_ats, name='check_ats'),
    path('cold-email/', views.cold_email, name='cold_email'),
    path('hr/session/start/', hr_interview.start_session, name='hr_session_start'),
    path('hr/session/answer/', hr_interview.answer_session, name='hr_session_answer'),
    path('hr/session/<int:session_id>/', hr_interview.session_detail, name='hr_session_detail'),
]
