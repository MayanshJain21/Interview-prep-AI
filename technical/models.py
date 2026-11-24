from django.contrib.auth.models import User
from django.db import models


class TechnicalInterviewSession(models.Model):
    PENDING, IN_PROGRESS, COMPLETED = 'pending', 'in_progress', 'completed'
    DIFFICULTIES = [('Easy', 'Easy'), ('Medium', 'Medium'), ('Hard', 'Hard')]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='technical_sessions')
    job_role = models.CharField(max_length=150, blank=True, default='')
    company = models.CharField(max_length=150, blank=True, default='')
    job = models.ForeignKey('jobs.JobDescription', null=True, blank=True, on_delete=models.SET_NULL)
    interview_type = models.CharField(max_length=30)
    difficulty = models.CharField(max_length=10, choices=DIFFICULTIES)
    num_questions = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=15, default=PENDING)
    level = models.PositiveSmallIntegerField(default=2)  # current adaptive level: 1 easy, 2 medium, 3 hard
    topic_plan = models.JSONField(default=list)  # [{"topic", "skill"}]
    resume_context = models.TextField(blank=True, default='')
    overall_score = models.FloatField(null=True, blank=True)
    report = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', 'status', '-created_at'])]


class TechnicalInterviewTurn(models.Model):
    OPEN, EVALUATING, ANSWERED = 'open', 'evaluating', 'answered'

    session = models.ForeignKey(TechnicalInterviewSession, on_delete=models.CASCADE, related_name='turns')
    number = models.PositiveSmallIntegerField()
    topic = models.CharField(max_length=100)
    skill = models.ForeignKey('learning.Skill', null=True, blank=True, on_delete=models.SET_NULL)
    difficulty = models.CharField(max_length=10)
    kind = models.CharField(max_length=20, default='core')  # core | deeper | probe | foundational
    question = models.TextField()
    answer = models.TextField(blank=True, default='')
    state = models.CharField(max_length=12, default=OPEN)
    score = models.FloatField(null=True, blank=True)  # 0-10, weighted from the rubric
    evaluation = models.JSONField(default=dict)
    asked_at = models.DateTimeField(auto_now_add=True)
    answered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['number']
        constraints = [models.UniqueConstraint(fields=['session', 'number'], name='unique_turn_number')]
