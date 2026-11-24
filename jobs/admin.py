from django.contrib import admin

from .models import JobDescription, JobRequirement, ResumeJobAnalysis

admin.site.register([JobDescription, JobRequirement, ResumeJobAnalysis])
