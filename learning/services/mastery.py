"""Mastery estimation. The estimator is a small class so another algorithm (e.g. Bayesian
Knowledge Tracing or Elo) can be added later and selected in one place."""
import math

from django.conf import settings
from django.utils import timezone


class EMAEstimator:
    """Exponential moving average: M_new = (1 - alpha) * M_old + alpha * P.

    The first piece of evidence sets the mastery directly (M = P): we never assume an untested
    student starts at 50%.
    """
    name = 'ema'

    def __init__(self, alpha):
        if not 0 < alpha <= 1:
            raise ValueError('alpha must be in (0, 1]')
        self.alpha = alpha

    def update(self, old, performance):
        performance = max(0.0, min(100.0, float(performance)))
        if old is None:
            return performance
        return (1 - self.alpha) * old + self.alpha * performance


def get_estimator():
    return EMAEstimator(settings.LEARNING_ENGINE['ALPHA'])


def confidence(attempts, last_assessed, now=None):
    """0-1 confidence in a mastery estimate: grows with the number of attempts and fades slowly
    when the skill hasn't been assessed for a while."""
    if not attempts:
        return 0.0
    now = now or timezone.now()
    k = settings.LEARNING_ENGINE['CONFIDENCE_ATTEMPTS']
    days = max(0, (now - last_assessed).days) if last_assessed else 0
    return round((1 - math.exp(-attempts / k)) * (0.5 + 0.5 * math.exp(-days / 60)), 2)


def band_for(mastery):
    """Difficulty band for a mastery value (None = unassessed -> the easiest band)."""
    bands = settings.LEARNING_ENGINE['DIFFICULTY_BANDS']
    if mastery is None:
        return bands[0]
    for band in bands:
        if mastery < band['below']:
            return band
    return bands[-1]


def status_for(mastery):
    if mastery is None:
        return 'unassessed'
    cfg = settings.LEARNING_ENGINE
    if mastery >= cfg['MASTERED']:
        return 'mastered'
    if mastery >= 75:
        return 'strong'
    if mastery >= cfg['PREREQ_THRESHOLD']:
        return 'developing'
    return 'weak'
