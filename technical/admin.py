from django.contrib import admin

from .models import TechnicalInterviewSession, TechnicalInterviewTurn

admin.site.register([TechnicalInterviewSession, TechnicalInterviewTurn])
