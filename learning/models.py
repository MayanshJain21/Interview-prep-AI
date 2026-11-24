from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models


class Skill(models.Model):
    """One node of the skill taxonomy. New skills are added as rows (or in taxonomy.py + a data
    migration), not hardcoded in feature code."""
    CATEGORIES = [
        ('programming', 'Programming'), ('dsa', 'DSA'), ('core_cs', 'Core CS'),
        ('web', 'Web Development'), ('tools', 'Tools'), ('data', 'Data & ML'), ('other', 'Other'),
    ]

    slug = models.SlugField(max_length=60, unique=True)
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=CATEGORIES)
    # An umbrella skill (e.g. "DSA") groups narrower ones; used for partial matches.
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='children')
    aliases = models.JSONField(default=list, blank=True)  # lowercase alternative names
    description = models.CharField(max_length=300, blank=True, default='')
    # Which existing modules can assess it: subset of ["mcq", "coding", "technical"].
    assessable_via = models.JSONField(default=list, blank=True)
    coding_topic = models.CharField(max_length=50, blank=True, default='')  # topic name used by the coding round
    interview_type = models.CharField(max_length=30, blank=True, default='')  # technical interview type

    class Meta:
        ordering = ['category', 'name']

    def __str__(self):
        return self.name


class SkillPrerequisite(models.Model):
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name='prerequisite_links')
    prerequisite = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name='unlocks_links')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['skill', 'prerequisite'], name='unique_skill_prerequisite'),
            models.CheckConstraint(condition=~models.Q(skill=models.F('prerequisite')), name='prerequisite_not_self'),
        ]

    def clean(self):
        from .services.taxonomy import would_create_cycle
        if would_create_cycle(self.skill_id, self.prerequisite_id):
            raise ValidationError('This prerequisite would create a cycle.')


class LearningGoal(models.Model):
    """What the student is preparing for. One active goal per user."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='learning_goal')
    target_role = models.CharField(max_length=150, blank=True, default='')
    job_analysis = models.ForeignKey('jobs.ResumeJobAnalysis', null=True, blank=True, on_delete=models.SET_NULL)
    deadline = models.DateField(null=True, blank=True)
    minutes_per_day = models.PositiveIntegerField(default=60)
    study_days = models.JSONField(default=list)  # weekday numbers, Monday = 0
    updated_at = models.DateTimeField(auto_now=True)


class LearningAttempt(models.Model):
    """One piece of assessment evidence for one skill. (source, source_ref, skill) is unique per
    user, so processing the same submission twice never double-counts it."""
    SOURCES = [('mcq', 'MCQ'), ('coding', 'Coding round'), ('technical', 'Technical interview')]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='learning_attempts')
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name='attempts')
    source = models.CharField(max_length=20, choices=SOURCES)
    source_ref = models.CharField(max_length=100)  # e.g. "mcq:12", "coding-problem:40", "technical-turn:7"
    score = models.FloatField()  # 0-100
    difficulty = models.CharField(max_length=10, blank=True, default='')
    correct = models.BooleanField(null=True, blank=True)
    hints_used = models.PositiveIntegerField(default=0)
    mastery_before = models.FloatField(null=True, blank=True)
    mastery_after = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'source', 'source_ref', 'skill'], name='unique_evidence')]
        indexes = [models.Index(fields=['user', 'skill', 'created_at'])]


class SkillMastery(models.Model):
    """Current estimate per (user, skill). No row = never assessed (unknown, not weak)."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='skill_mastery')
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE)
    mastery = models.FloatField()  # 0-100
    attempts = models.PositiveIntegerField(default=0)
    last_assessed = models.DateTimeField()
    sources = models.JSONField(default=dict)  # {"mcq": 2, "coding": 1}
    algorithm = models.CharField(max_length=20, default='ema')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'skill'], name='unique_user_skill_mastery')]


class LearningRoadmap(models.Model):
    ACTIVE, ARCHIVED = 'active', 'archived'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='roadmaps')
    status = models.CharField(max_length=10, default=ACTIVE)
    target_role = models.CharField(max_length=150, blank=True, default='')
    job_analysis = models.ForeignKey('jobs.ResumeJobAnalysis', null=True, blank=True, on_delete=models.SET_NULL)
    start_date = models.DateField()
    deadline = models.DateField()
    minutes_per_day = models.PositiveIntegerField()
    study_days = models.JSONField(default=list)
    summary = models.JSONField(default=dict)  # unscheduled work, config used, milestones
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['user', 'status'])]


class RoadmapItem(models.Model):
    PENDING, COMPLETED, SKIPPED = 'pending', 'completed', 'skipped'
    TYPES = [('diagnostic', 'Diagnostic'), ('learn', 'Learn'), ('mcq', 'MCQ practice'), ('coding', 'Coding practice'),
             ('interview', 'Technical interview'), ('revision', 'Revision'), ('assessment', 'Weekly assessment'),
             ('self_study', 'Self study')]

    roadmap = models.ForeignKey(LearningRoadmap, on_delete=models.CASCADE, related_name='items')
    skill = models.ForeignKey(Skill, null=True, blank=True, on_delete=models.SET_NULL)
    title = models.CharField(max_length=200)
    activity_type = models.CharField(max_length=20, choices=TYPES)
    difficulty = models.CharField(max_length=10, blank=True, default='')
    scheduled_date = models.DateField()
    duration_min = models.PositiveIntegerField()
    week = models.PositiveIntegerField(default=1)
    order = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=10, default=PENDING)
    reason = models.CharField(max_length=300, blank=True, default='')
    link = models.JSONField(default=dict)  # {"path": "/mcq", "params": {...}} for the "Start" button
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['scheduled_date', 'order']
        indexes = [models.Index(fields=['roadmap', 'status', 'scheduled_date'])]
