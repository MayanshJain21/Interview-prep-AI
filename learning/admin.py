from django.contrib import admin

from .models import (LearningAttempt, LearningGoal, LearningRoadmap, RoadmapItem, Skill, SkillMastery,
                     SkillPrerequisite)


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'category', 'parent')
    list_filter = ('category',)
    search_fields = ('name', 'slug')


@admin.register(SkillPrerequisite)
class SkillPrerequisiteAdmin(admin.ModelAdmin):
    list_display = ('skill', 'prerequisite')

    def save_model(self, request, obj, form, change):
        obj.full_clean()  # runs the cycle check
        super().save_model(request, obj, form, change)


admin.site.register([LearningGoal, LearningAttempt, SkillMastery, LearningRoadmap, RoadmapItem])
