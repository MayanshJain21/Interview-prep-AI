from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('SECRET_KEY')

DEBUG = True

ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',

    'users',
    'resume',
    'ai_features',
    'dashboard',
    'coding',
    'learning',
    'jobs',
    'technical',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'backend.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

STATIC_URL = 'static/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CORS_ALLOW_ALL_ORIGINS = True

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
}

from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'SIGNING_KEY': os.getenv('JWT_SECRET', SECRET_KEY),
}

GROQ_API_KEY = os.getenv('GROQ_API_KEY')
# Google sign-in: the OAuth Web client ID (public, not a secret). Empty = the Google button is hidden.
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '').strip()

# ---------------------------------------------------------------- Part 2 configuration

# Resume <-> job description matching (see docs/ALGORITHMS.md). Weights are renormalised over the
# components that actually have data for a given job.
JOB_MATCH = {
    'WEIGHTS': {'required': 0.70, 'preferred': 0.20, 'experience_qualification': 0.10},
    'PARTIAL_CREDIT': 0.5,       # a partially matched skill counts as half a match
    'MAX_JD_CHARS': 20000,
    'MAX_PDF_BYTES': 2 * 1024 * 1024,
    'MAX_PDF_PAGES': 20,
}

# Adaptive learning engine (see docs/ALGORITHMS.md).
LEARNING_ENGINE = {
    'ALPHA': 0.3,                # EMA update factor
    'PREREQ_THRESHOLD': 60,      # a prerequisite below this mastery blocks the skills that need it
    'MASTERED': 90,
    'DIAGNOSTIC_PRIORITY_GAP': 60,  # stand-in gap used ONLY to rank unassessed skills for a diagnostic
    'STALE_DAYS': 14,            # practice older than this gets a revision boost
    'STALE_BOOST_MAX': 0.5,
    'CONFIDENCE_ATTEMPTS': 3,    # attempts needed for ~63% confidence
    'REQUIRED_IMPORTANCE': 1.0,
    'PREFERRED_IMPORTANCE': 0.6,
    # Upper bound (exclusive) of each mastery band -> recommended difficulty per module.
    'DIFFICULTY_BANDS': [
        {'below': 40, 'label': 'Fundamentals', 'mcq': 'Easy', 'coding': 'easy', 'interview': 'Easy'},
        {'below': 60, 'label': 'Easy to medium', 'mcq': 'Medium', 'coding': 'easy', 'interview': 'Easy'},
        {'below': 75, 'label': 'Medium', 'mcq': 'Medium', 'coding': 'medium', 'interview': 'Medium'},
        {'below': 90, 'label': 'Hard', 'mcq': 'Hard', 'coding': 'hard', 'interview': 'Hard'},
        {'below': 101, 'label': 'Advanced and revision', 'mcq': 'Hard', 'coding': 'hard', 'interview': 'Hard'},
    ],
    'ACTIVITY_MINUTES': {'diagnostic': 20, 'learn': 45, 'mcq': 20, 'coding': {'easy': 30, 'medium': 45, 'hard': 60},
                         'interview': 30, 'revision': 30, 'assessment': 45, 'self_study': 45},
}

# Rate limits for the AI-heavy endpoints (DRF scoped throttling).
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {'llm': '20/min', 'llm_burst': '6/min', 'auth': '20/min'}
