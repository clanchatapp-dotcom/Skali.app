import os
import pytest
import requests

BASE_URL = os.environ.get(
    'EXPO_BACKEND_URL',
    'https://1364d24c-2629-41c4-b227-b4ccdd97873e.preview.emergentagent.com',
).rstrip('/')

STEP_UP_SECRET = 'fEFGyT51RQ06GTkezQeZ-9lMjCYNyjTv'
ADMIN_EMAIL = 'admin@skaliapp.com'
ADMIN_PASSWORD = 'SkaliLocalDev!2026'


@pytest.fixture(scope='session')
def base_url():
    return BASE_URL


@pytest.fixture(scope='session')
def api():
    s = requests.Session()
    s.headers.update({'Content-Type': 'application/json'})
    return s
