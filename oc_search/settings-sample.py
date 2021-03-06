"""
Django settings for oc_search project.

Generated by 'django-admin startproject' using Django 3.0.5.

For more information on this file, see
https://docs.djangoproject.com/en/3.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.0/ref/settings/
"""
from django.utils.translation import gettext_lazy as _
import os

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'Replace_this_key_with_a_random_value!'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = [
    'jazzmin',
    'import_export',
    'django.contrib.admin',
    'django.contrib.admindocs',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.humanize',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'search'
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'oc_search.middleware.CanadaBilingualMiddleware'
]

ROOT_URLCONF = 'oc_search.urls'

STATIC_ROOT = os.path.join(BASE_DIR, 'static')

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.0/howto/static-files/

STATIC_URL = '/static/'

STATICFILES_DIRS = [
    ('cdts', os.path.join(BASE_DIR, "cdts", "v4_0_32")),
    ('search_snippets', os.path.join(BASE_DIR, 'search', 'templates', 'snippets')),
]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'static'),
                 os.path.join(BASE_DIR, 'search', 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'oc_search.wsgi.application'


# Database
# https://docs.djangoproject.com/en/3.0/ref/settings/#databases

# The search application specifies a separate configuration for the main functions of the search application
# Future plugins are free to add other databaes if required but should not use the default database, or
# the default Database router defined in the db_router.py class, but should instead add their own router.

DATABASES = {
    'default': {
        'ENGINE': '',
    },
    'search': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

DATABASE_ROUTERS = ['search.db_router.SearchRouter']

# Password validation
# https://docs.djangoproject.com/en/3.0/ref/settings/#auth-password-validators

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


# Internationalization
# https://docs.djangoproject.com/en/3.0/topics/i18n/

LANGUAGE_CODE = 'en'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_L10N = True
USE_TZ = True
LANGUAGES = [
    ('en', _('English')),
    ('fr', _('French')),
]

LOCALE_PATHS = [
    os.path.join(BASE_DIR, 'locale'),
]

# File cache directory used by the export search results feature. If files are served by a web server like Nginx
# or Apache, set the FILE_CACHE_URL

EXPORT_FILE_CACHE_DIR = os.path.join(BASE_DIR, 'cache')
EXPORT_FILE_CACHE_URL = ""

# Solr Search Configuration

SOLR_SERVER_URL = 'http://localhost:8983/solr'

SOLR_COLLECTION = "SolrClient_unittest"

# Application URL

SEARCH_EN_HOSTNAME = ''
SEARCH_FR_HOSTNAME = ''
SEARCH_HOST_PATH = ''
SEARCH_LANG_USE_PATH = True

# Active CDTS Version

CDTS_VERSION = 'v4_0_32'

ANALYTICS_JS = ""

# Logging

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}

MARKDOWN_FILTER_WHITELIST_TAGS = [
    'a',
    'p',
    'code',
    'em',
    'h1', 'h2', 'h3', 'h4',
    'ul',
    'ol',
    'li',
    'br',
    'mark',
    'pre',
    'strong',
    'table', 'thead', 'th', 'tr', 'tbody', 'td'
]
MARKDOWN_FILTER_EXTRAS = ["tables", "break-on-newline"]

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}

SESSION_ENGINE="django.contrib.sessions.backends.file"
SESSION_FILE_PATH = os.path.join(BASE_DIR, 'session')
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

ADOBE_ANALYTICS_URL = ''
GOOGLE_ANALYTICS_GTM_ID = ''
GOOGLE_ANALYTICS_PROPERTY_ID = ''

IMPORT_EXPORT_USE_TRANSACTIONS = False