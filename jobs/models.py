from django.contrib.auth.models import User
from django.db import models


class JobDescription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='job_descriptions')
    title = models.CharField(max_length=150)
    company = models.CharField(max_length=150, blank=True, default='')
    target_role = models.CharField(max_length=150, blank=True, default='')
    text = models.TextField()
    source = models.CharField(max_length=10, default='paste')  # paste | pdf
    extracted = models.JSONField(default=dict, blank=True)  # validated LLM extraction, reused by re-analysis
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', '-created_at'])]

    def __str__(self):
        return f'{self.title} @ {self.company}' if self.company else self.title


class JobRequirement(models.Model):
    IMPORTANCE = [('required', 'Required'), ('preferred', 'Preferred')]

    job = models.ForeignKey(JobDescription, on_delete=models.CASCADE, related_name='requirements')
    name = models.CharField(max_length=120)  # as written in the job description
    skill = models.ForeignKey('learning.Skill', null=True, blank=True, on_delete=models.SET_NULL)  # canonical skill
    kind = models.CharField(max_length=20, default='technical')  # technical | language | tool
    importance = models.CharField(max_length=10, choices=IMPORTANCE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['job', 'name'], name='unique_job_requirement')]


class ResumeJobAnalysis(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='job_analyses')
    job = models.ForeignKey(JobDescription, on_delete=models.CASCADE, related_name='analyses')
    resume_filename = models.CharField(max_length=255, blank=True, default='')
    overall_score = models.FloatField()  # resume-job alignment, NOT a hiring probability
    technical_score = models.FloatField()
    breakdown = models.JSONField(default=dict)  # components, weights, formula
    skill_matches = models.JSONField(default=list)
    recommendations = models.JSONField(default=list)
    preparation_areas = models.JSONField(default=list)
    relevant_sections = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', '-created_at'])]
