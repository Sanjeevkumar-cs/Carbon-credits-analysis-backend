"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os
from django.core.wsgi import get_wsgi_application

# Auto-detect if we are on Render. If yes, use deployment settings. If no, use local settings.
settings_module = 'config.deployment_settings' if 'RENDER_EXTERNAL_HOSTNAME' in os.environ else 'config.settings'

os.environ.setdefault('DJANGO_SETTINGS_MODULE', settings_module)

application = get_wsgi_application()