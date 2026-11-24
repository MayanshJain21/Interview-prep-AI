from django.db import models
from django.contrib.auth.models import User


class MCQHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mcq_history')
    score = models.IntegerField(default=0)
    total = models.IntegerField(default=10)
    skills = models.JSONField(default=list)
    attempt_id = models.CharField(max_length=64, blank=True, default='')  # client id, makes resubmits idempotent
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.score}/{self.total}"


class ATSHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ats_history')
    score = models.IntegerField(default=0)
    tips = models.JSONField(default=list)
    role = models.CharField(max_length=80, blank=True, default='')
    role_fit = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - ATS {self.score}"


class HRSession(models.Model):
    """One full mock interview: a fixed number of questions that adapt to the candidate's answers."""
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_COMPLETED = 'completed'
    STATUS_CHOICES = [
        (STATUS_IN_PROGRESS, 'In progress'),
        (STATUS_COMPLETED, 'Completed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hr_sessions')
    job_role = models.CharField(max_length=255, blank=True, default='')
    total_questions = models.IntegerField(default=6)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_IN_PROGRESS)
    # Resume context is retrieved once at the start so every question draws on the same facts.
    resume_context = models.TextField(blank=True, default='')
    overall_score = models.IntegerField(default=0)
    report = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - HR session {self.id} ({self.status})"


class HRHistory(models.Model):
    """A single question/answer turn. Turns without a session come from the old single-question flow."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hr_history')
    session = models.ForeignKey(HRSession, on_delete=models.CASCADE, related_name='turns', null=True, blank=True)
    question_number = models.IntegerField(default=1)
    stage = models.CharField(max_length=50, blank=True, default='')
    question = models.TextField(default='')
    answer = models.TextField(default='')
    score = models.IntegerField(default=0)
    feedback = models.TextField(default='')
    strengths = models.JSONField(default=list)
    improvements = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - HR {self.score}/10"
