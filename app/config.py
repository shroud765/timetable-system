"""Shared settings. MySQL is required except for explicit test mode."""
import os

DATABASE_URL = os.environ.get('DATABASE_URL', '')
TESTING = os.environ.get('TESTING') == '1'
if not DATABASE_URL.startswith('mysql+pymysql://'):
    if not (TESTING and DATABASE_URL.startswith('sqlite')):
        raise RuntimeError('Set DATABASE_URL to mysql+pymysql://...')
ORIGIN = os.environ.get('APP_ORIGIN', 'http://127.0.0.1:8000')
SECURE_COOKIE = ORIGIN.startswith('https://')
GATEWAY_URL = os.environ.get('GATEWAY_URL', '')
GATEWAY_TOKEN = os.environ.get('GATEWAY_TOKEN', '')
MAX_PERIODS = 6
DAYS = 5

