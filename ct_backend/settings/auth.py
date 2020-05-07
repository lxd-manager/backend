import os

AUTHENTICATION_BACKENDS = (
    'social_core.backends.gitlab.GitLabOAuth2',
    'django.contrib.auth.backends.ModelBackend',
)

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'apps.account.drf.IsStaff',
    ]
}
if os.environ.get('DJANGO_CSRF_EXCEPT', False):
    REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES'] = [
        'apps.account.drf.CsrfExemptSessionAuthentication',
        'rest_framework.authentication.BasicAuthentication'
    ]


SOCIAL_AUTH_GITLAB_API_URL = os.environ.get('SOCIAL_AUTH_GITLAB_API_URL', 'https://localhost/')

LOGIN_REDIRECT_URL = '/'
