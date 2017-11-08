import hashlib as _hashlib
import os as _os
import random as _random
import warnings as _warnings

from unipath import Path as _Path

is_ci = _os.environ.get('CI_SERVER', 'no') == 'yes'

BASE_DIR = _Path(__file__).parent

_db_vars = {
    'HOST': ('MYSQL_HOST', None),
    'USER': ('MYSQL_USER', None),
    'PASSWORD': ('MYSQL_PASSWORD', None),
    'NAME': ('MYSQL_DATABASE', 'alliance_django_utils'),
}
_db_vars = {var: _os.environ.get(env_var, default) for var, (env_var, default) in _db_vars.items()}
_db_vars = {key: value for key, value in _db_vars.items() if value}
_db_vars['ENGINE'] = 'django.db.backends.mysql'
_db_vars['OPTIONS'] = {
    'init_command': 'SET default_storage_engine=InnoDB',
    'read_default_file': '~/.my.cnf',
}

# Django connects via the live DB in order to create/drop the test DB
# If the live DB doesn't exist then it bails out before even trying to
# create the test DB, so this doesn't really work
# if is_ci:
#     db_vars['TEST'] = {
#         'NAME': db_vars['NAME'],
#     }

DATABASES = {'default': _db_vars}

INSTALLED_APPS = (
    'allianceutils',
    'test_allianceutils',
    'test_allianceutils.tests.autodumpdata',
    'test_allianceutils.tests.checks',
    'test_allianceutils.tests.middleware',
    'test_allianceutils.tests.profile_auth',
    'test_allianceutils.tests.serializers',

    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
)

AUTH_USER_MODEL = 'profile_auth.GenericUserProfile'

MIDDLEWARE = ()

TEMPLATE_DIRS = (
    # os.path.join(BASE_DIR, 'compat/tests/templates/')
)

TEMPLATES = (
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'APP_DIRS': True,
        'DIRS': TEMPLATE_DIRS,
    },
)

STATIC_ROOT = _Path(BASE_DIR, 'static')

SERIALIZATION_MODULES = {
    'json_ordered': 'allianceutils.serializers.json_ordered',
    'json': 'allianceutils.serializers.json_orminheritancefix',
}

ROOT_URLCONF = 'test_allianceutils.urls'

SECRET_KEY = _hashlib.sha256(str(_random.SystemRandom().getrandbits(256)).encode('ascii')).hexdigest()

QUERY_COUNT_WARNING_THRESHOLD = 40

_warnings.simplefilter('always')
