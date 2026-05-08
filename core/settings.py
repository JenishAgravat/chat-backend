import os
from pathlib import Path
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

# ─── Security ───
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-((_3$r+urkcl62kdnnwcn+f)ul)k_lqrw%#lzr0z7rpvh17(uk')
DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'
ALLOWED_HOSTS = [
    host.replace('https://', '').replace('http://', '').strip('/') 
    for host in os.environ.get('ALLOWED_HOSTS', '*').split(',')
]

CSRF_TRUSTED_ORIGINS = [
    f"https://{host}" if not host.startswith('http') else host
    for host in ALLOWED_HOSTS if host != '*'
]
# Ensure localhost is trusted in dev if not already there
if DEBUG:
    CSRF_TRUSTED_ORIGINS += ["http://localhost:8000", "http://127.0.0.1:8000"]

# Handle Render's specific environment variable
render_host = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if render_host:
    CSRF_TRUSTED_ORIGINS.append(f"https://{render_host}")

# Explicitly add your specific Render domain to be 100% sure
CSRF_TRUSTED_ORIGINS.append("https://chat-backend-nmg2.onrender.com")

# ─── Apps ───
INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'graphene_django',
    'channels',
    'chat',
    'graphql_jwt.refresh_token',
]

# ─── Middleware ───
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

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

WSGI_APPLICATION = 'core.wsgi.application'
ASGI_APPLICATION = 'core.asgi.application'

# ─── Channel Layer (Redis in prod, InMemory in dev) ───
RAW_REDIS_URL = os.environ.get('REDIS_URL', '').strip()
if RAW_REDIS_URL:
    import re
    # Debug print to see EXACTLY what is in the environment
    print(f"--- REDIS DEBUG START ---")
    print(f"RAW_REDIS_URL: '{RAW_REDIS_URL}'")
    
    # 1. Clean quotes
    temp_url = RAW_REDIS_URL.strip("'").strip('"').strip()
    
    # 2. Try to extract a full URL (redis:// or rediss://)
    url_match = re.search(r'(rediss?://[^\s\'"]+)', temp_url)
    if url_match:
        REDIS_URL = url_match.group(1)
    else:
        # 3. Try to extract what follows the -u flag
        u_match = re.search(r'-u\s+([^\s\'"]+)', temp_url)
        if u_match:
            REDIS_URL = u_match.group(1)
        else:
            # 4. Fallback: take the last non-whitespace part (likely the host:port)
            parts = temp_url.split()
            REDIS_URL = parts[-1] if parts else temp_url
    
    # Final cleanup of any trailing garbage or quotes
    REDIS_URL = REDIS_URL.strip("'").strip('"').rstrip('/')
    
    # Ensure URL starts with redis:// or rediss:// if it's just host:port
    if not (REDIS_URL.startswith('redis://') or REDIS_URL.startswith('rediss://')):
        REDIS_URL = f"redis://{REDIS_URL}"
    
    print(f"CLEANED_REDIS_URL: '{REDIS_URL}'")
    print(f"--- REDIS DEBUG END ---")
        
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [REDIS_URL],
                "socket_timeout": 5,
                "socket_connect_timeout": 5,
            },
        }
    }
else:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer"
        }
    }

# ─── Database (PostgreSQL in prod, SQLite in dev) ───
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    import dj_database_url
    DATABASES = {
        'default': dj_database_url.config(default=DATABASE_URL, conn_max_age=0)
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_USER_MODEL = 'chat.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ─── Static files ───
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

# ─── GraphQL / JWT ───
GRAPHENE = {
    'SCHEMA': 'core.schema.schema',
    'MIDDLEWARE': [
        'graphql_jwt.middleware.JSONWebTokenMiddleware',
    ],
}

AUTHENTICATION_BACKENDS = [
    'graphql_jwt.backends.JSONWebTokenBackend',
    'django.contrib.auth.backends.ModelBackend',
]

GRAPHQL_JWT = {
    'JWT_VERIFY_EXPIRATION': True,
    'JWT_EXPIRATION_DELTA': timedelta(minutes=60),
    'JWT_REFRESH_EXPIRATION_DELTA': timedelta(days=7),
}
