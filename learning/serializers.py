from rest_framework import serializers

from .models import LearningRoadmap, RoadmapItem


class GenerateRoadmapSerializer(serializers.Serializer):
    target_role = serializers.CharField(max_length=150, allow_blank=True, required=False, default='')
    job_analysis_id = serializers.IntegerField(required=False, allow_null=True)
    deadline = serializers.DateField()
    minutes_per_day = serializers.IntegerField(min_value=15, max_value=600)
    study_days = serializers.ListField(child=serializers.IntegerField(min_value=0, max_value=6), allow_empty=False)


class ItemStatusSerializer(serializers.Serializer):
    item_id = serializers.IntegerField()
    status = serializers.ChoiceField(choices=['completed', 'skipped', 'pending'], default='completed')


class RescheduleSerializer(serializers.Serializer):
    item_id = serializers.IntegerField()
    date = serializers.DateField()


class RoadmapItemSerializer(serializers.ModelSerializer):
    skill = serializers.CharField(source='skill.name', default=None)
    skill_slug = serializers.CharField(source='skill.slug', default=None)

    class Meta:
        model = RoadmapItem
        fields = ['id', 'title', 'activity_type', 'difficulty', 'scheduled_date', 'duration_min', 'week', 'status',
                  'reason', 'link', 'completed_at', 'skill', 'skill_slug']


class RoadmapSerializer(serializers.ModelSerializer):
    items = RoadmapItemSerializer(many=True, read_only=True)
    job_title = serializers.CharField(source='job_analysis.job.title', default=None)

    class Meta:
        model = LearningRoadmap
        fields = ['id', 'status', 'target_role', 'job_analysis', 'job_title', 'start_date', 'deadline',
                  'minutes_per_day', 'study_days', 'summary', 'created_at', 'items']
