import asyncio
import datetime
import json
import logging
import os
import sqlite3
import ssl
from threading import Lock, Thread

from dotenv import dotenv_values
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse
from oauthlib.oauth2 import WebApplicationClient
import pika
from pika.adapters.blocking_connection import BlockingChannel
import requests
import uvicorn

from oauth_utils import get_google_provider_cfg
from utils import consume_pika_query, encode_message, fetch


logging.basicConfig(level=logging.INFO)

CONFIG = dotenv_values('.env')
GOOGLE_CLIENT_ID = CONFIG.get('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = CONFIG.get('GOOGLE_CLIENT_SECRET', os.urandom(24))
GOOGLE_DISCOVERY_URL = CONFIG.get('GOOGLE_DISCOVERY_URL')
BOT_LINK = CONFIG.get('BOT_LINK')

# FastAPI app setup
app = FastAPI()
app.secret_key = GOOGLE_CLIENT_SECRET


# OAuth2 client setup
OAUTH_CLIENT = WebApplicationClient(GOOGLE_CLIENT_ID)

def publish_callback_message_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()
    return

def get_register_notifications_queue():
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    notifications_channel = connection.channel()
    notifications_channel.queue_declare(queue='vika_callbacks')
    return notifications_channel

async def publish_callback_token(
            token: dict,
            notifications_queue: BlockingChannel=get_register_notifications_queue(),
            oauth_client=WebApplicationClient(GOOGLE_CLIENT_ID),
            provider_cfg=get_google_provider_cfg()
        ):
    token_json = json.dumps(token)
    oauth_client.parse_request_body_response(token_json)
    uri, headers, body = oauth_client.add_token(provider_cfg['userinfo_endpoint'])
    userinfo_response = requests.get(uri, headers=headers, data=body)
    userinfo_json = userinfo_response.json()

    message = {
        'google_unique_id': userinfo_json['sub'],
        'email': userinfo_json['email'],
        'verified': userinfo_json.get('email_verified', False),
        'username': userinfo_json['name'],
        'token_register_datetime': datetime.datetime.now().isoformat()
    }
    message.update(token)
    message = encode_message(message)
    notifications_queue.basic_publish(
        exchange='',
        routing_key='vika_callbacks',
        body=message
    )
    return

@app.get("/login/callback")
async def callback(request: Request, code: str):
    """
    После авторизации юзер перенаправляется сюда
    Для его авторизации у гугла запрашивается токен
    """
    print(str(request))
    print('auth code:', code)

    # Get authorization code Google sent back to you
    google_provider_cfg = get_google_provider_cfg()
    token_endpoint = google_provider_cfg['token_endpoint']
    token_url, headers, body = OAUTH_CLIENT.prepare_token_request(
        token_endpoint,
        authorization_response=str(request.url),
        redirect_url=request.url_for('callback'),
        code=code,
    )

    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
    )
    token_json = token_response.json()
    print("User token:", type(token_json), token_json)

    asyncio.run_coroutine_threadsafe(publish_callback_token(token_json), app.state.publish_loop)

    # redirect to a bot
    response = RedirectResponse(url=BOT_LINK)
    return response

if __name__ == "__main__":
    uvicorn.run(app, host='0.0.0.0', port=5000, ssl_keyfile='key.pem', ssl_certfile='cert.pem')
