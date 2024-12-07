import os
import requests

from dotenv import dotenv_values


CONFIG = dotenv_values('.env')
GOOGLE_CLIENT_ID = CONFIG.get('GOOGLE_CLIENT_ID', None)
GOOGLE_CLIENT_SECRET = CONFIG.get('GOOGLE_CLIENT_SECRET', os.urandom(24))
GOOGLE_DISCOVERY_URL = CONFIG.get('GOOGLE_DISCOVERY_URL', None)

def get_google_provider_cfg():
    # Find out what URL to hit to get tokens that allow you to ask for
    # things on behalf of a user
    provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
    return provider_cfg
