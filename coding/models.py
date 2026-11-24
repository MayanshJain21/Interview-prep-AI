from django.contrib.auth.models import User
from django.db import models


class CodingSession(models.Model):
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='coding_sessions')
    job_role = models.CharField(max_length=255, blank=True, default='')
    difficulty = models.CharField(max_length=10)
    language = models.CharField(max_length=20, default='python')
    status = models.CharField(max_length=20, default=IN_PROGRESS)
    time_limit_sec = models.IntegerField()
    started_at = models.DateTimeField(auto_now_add=True)
    ends_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    overall_score = models.IntegerField(default=0)
    report = models.JSONField(default=dict)
    paste_flags = models.IntegerField(default=0)
    tab_switches = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.user.username} - coding {self.difficulty} ({self.status})"


class CodingProblem(models.Model):
    """A copy of a bank problem for one session, so later bank edits don't change old reports."""
    session = models.ForeignKey(CodingSession, on_delete=models.CASCADE, related_name='problems')
    order = models.IntegerField()
    bank_id = models.CharField(max_length=100)
    topic = models.CharField(max_length=50)
    title = models.CharField(max_length=200)
    data = models.JSONField()  # full bank entry, including hidden tests and the reference
    hints_used = models.IntegerField(default=0)
    saved_code = models.JSONField(default=dict)  # {language: code}

    class Meta:
        ordering = ['order']


class CodingSubmission(models.Model):
    RUN = 'run'
    SUBMIT = 'submit'

    problem = models.ForeignKey(CodingProblem, on_delete=models.CASCADE, related_name='submissions')
    kind = models.CharField(max_length=10)
    language = models.CharField(max_length=20)
    code = models.TextField()
    passed = models.IntegerField(default=0)
    total = models.IntegerField(default=0)
    results = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)


class PreparedProblem(models.Model):
    """A bank question already turned into a checked problem (statement, tests, reference solution).
    Writing one takes the LLM 15-60 s, so it is done once and reused by every later round."""
    slug = models.CharField(max_length=120, unique=True)  # LeetCode slug from the question bank
    difficulty = models.CharField(max_length=10, db_index=True)
    data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.slug
