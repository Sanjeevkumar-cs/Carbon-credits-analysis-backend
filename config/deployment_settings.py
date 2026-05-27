import os
import dj_database_url
from .settings import * # Imports all your local settings first

# 1. SECURITY: Force DEBUG to False in production
DEBUG = False

# 2. HOSTS: Render dynamically assigns a hostname. We capture it from the environment.
ALLOWED_HOSTS = [os.environ.get('RENDER_EXTERNAL_HOSTNAME', '*')]

# 3. DATABASE: Render provides a single 'DATABASE_URL'. dj_database_url parses it automatically.
DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL'),
        conn_max_age=600    # Keeps DB connections alive for 10 minutes to improve performance
    )
}

# 4. STATIC FILES: Enable WhiteNoise compression and caching for production
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# 5. CORS: Restrict API access to your exact frontend URL
CORS_ALLOW_ALL_ORIGINS = False

# Add your frontend URL (e.g., your React app's Render URL) here
FRONTEND_URL = os.environ.get('FRONTEND_URL', '')
if FRONTEND_URL:
    CORS_ALLOWED_ORIGINS = [FRONTEND_URL]