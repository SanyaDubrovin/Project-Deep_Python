import json
import os
import sqlite3
import uvicorn
import requests
import ssl
import pika

from threading import Lock, Thread
from dotenv import dotenv_values
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import RedirectResponse, HTMLResponse
from oauthlib.oauth2 import WebApplicationClient

from fastapi import Request

from utils import fetch, consume_pika_query
from oauth_utils import get_google_provider_cfg

from db import get_db


CONFIG = dotenv_values('.env')
GOOGLE_CLIENT_ID = CONFIG.get('GOOGLE_CLIENT_ID', None)
GOOGLE_CLIENT_SECRET = CONFIG.get('GOOGLE_CLIENT_SECRET', os.urandom(24))
GOOGLE_DISCOVERY_URL = CONFIG.get('GOOGLE_DISCOVERY_URL', None)
BOT_LINK = CONFIG.get('BOT_LINK', None)

# FastAPI app setup
app = FastAPI()
app.secret_key = GOOGLE_CLIENT_SECRET


try:
    DATABASE_CONNECTION = get_db()
except sqlite3.OperationalError:
    pass

# OAuth2 client setup
client = WebApplicationClient(GOOGLE_CLIENT_ID)
OAUTH_CLIENT = WebApplicationClient(GOOGLE_CLIENT_ID)

PIKA_EMAILS_LOCK = Lock()
PIKA_EMAILS_TO_REGISTER = set()

def pika_email_register_callback(ch, method, properties, body):
    with PIKA_EMAILS_LOCK:
        PIKA_EMAILS_TO_REGISTER.add(body.decode())
    return

def init_rabbitmq_connection() -> None:
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    consume_channel = connection.channel()
    consume_channel.queue_declare(queue='vika_register')

    send_channel = connection.channel()
    send_channel.queue_declare(queue='vika_notify')
    return consume_channel, send_channel

def send_message_to_rabbitmq(channel, queue_name, message) -> None:
    channel.basic_publish(exchange='', routing_key=queue_name, body=message)
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
    token_endpoint = google_provider_cfg["token_endpoint"]
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
    
    OAUTH_CLIENT.parse_request_body_response(json.dumps(token_json))

    # Get user info from Google using a token
    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = OAUTH_CLIENT.add_token(userinfo_endpoint)
    print('uri with token:', uri)
    userinfo_response = requests.get(uri, headers=headers, data=body)
    userinfo_json = userinfo_response.json()
    print('userinfo json:', userinfo_json)

    # check email verification
    if userinfo_json.get("email_verified"):
        unique_id = userinfo_json["sub"]
        users_email = userinfo_json["email"]
        users_name = userinfo_json["given_name"]
    else:
        raise HTTPException(status_code=400, detail="User email not available or not verified by Google.")

    PIKA_NOTIFY_CHANNEL.basic_publish(
                exchange='',
                routing_key='vika_notify',
                body=f'{users_email}\tUser {users_name} is registered!'
            )
    DATABASE_CONNECTION.update_user_info_by_email(
        userinfo_json['email'],
        username=users_name,
        status='verified',
    )

    # Begin user session by logging the user in
    print(PIKA_EMAILS_TO_REGISTER)
    if userinfo_json['email'] in PIKA_EMAILS_TO_REGISTER:
        print('User registered!')
    else:
        print('Unknown user!')
    # redirect to a bot
    response = RedirectResponse(url=BOT_LINK)
    return response


if __name__ == "__main__":
    PIKA_CONSUME_CHANNEL, PIKA_NOTIFY_CHANNEL = init_rabbitmq_connection()
    PIKA_CONSUMER_THREAD = Thread(target=consume_pika_query, args=(PIKA_CONSUME_CHANNEL, 'vika_register', pika_email_register_callback))
    PIKA_CONSUMER_THREAD.start()
    uvicorn.run(app, host='0.0.0.0', port=5000, ssl_keyfile='key.pem', ssl_certfile='cert.pem')
    PIKA_CONSUMER_THREAD.join()
