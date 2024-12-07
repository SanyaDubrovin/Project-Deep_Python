import asyncio
import aiohttp
import logging
import json
import re
import pika
import sqlite3

from threading import Thread, Lock
from enum import Enum
from dotenv import dotenv_values
from oauthlib.oauth2 import WebApplicationClient

from aiogram import Bot, Dispatcher, types, html
from aiogram.filters.command import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.formatting import as_list, as_marked_section, Text, Bold, HashTag, TextLink
from aiogram.enums import ParseMode
from aiogram import F

from utils import fetch, consume_pika_query
from db import get_db


EMAIL_REGEX = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'

logging.basicConfig(level=logging.INFO)
CONFIG = dotenv_values()
CALLBACK_URL = CONFIG.get('CALLBACK_URL', None)
SUPPORTED_EMAIL_DOMAINS = {'gmail',}
class SupportedEmails(Enum):
    gmail = 'gmail.com'

dp = Dispatcher()
TELEGRAM_BOT = Bot(
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML
    ),
    token=CONFIG['TOKEN']
)


"""
Message:
- message_id
- date
- chat
- from_user
"""

"""
Chat:
- id
"""

"""
User:
- id
- is_bot
- first_name
- last_name
- username (@username)
- full_name (first_name + last_name, если есть)
- url (ссылка на юзера)
"""

def init_rabbitmq_connection() -> None:
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    send_channel = connection.channel()
    send_channel.queue_declare(queue='vika_register')

    consume_channel = connection.channel()
    consume_channel.queue_declare(queue='vika_notify')
    return consume_channel, send_channel

def consume_pika_query(channel, queue_name, callback):
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    consume_channel = connection.channel()
    consume_channel.queue_declare(queue=queue_name)
    consume_channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)
    consume_channel.start_consuming()
    return

def pika_user_register_callback(ch, method, properties, body):
    email, message = body.decode().split('\t')
    # update dict of users
    new_user = DATABASE_CONNECTION.get_user_by_email(email)
    USERS_DICT.update(new_user)
    asyncio.run(send_message(new_user[email]['chat_id'], message))
    # loop = asyncio.get_event_loop()
    # loop.run_until_complete(send_message(new_user[email]['chat_id'], message))

async def send_message(chat_id: str, message: str):
    TELEGRAM_BOT.send_message(chat_id, message)
    return

def get_auth_client():
    return WebApplicationClient(CONFIG['GOOGLE_CLIENT_ID'])

def format_mail_message():
    """
    """

def validate_email(email: str) -> bool:
    """
    """
    if re.match(EMAIL_REGEX, email):
        return True
    return False

def get_email_schema(email: str):
    return email.split('@')[-1]

async def send_mail_message():
    """
    """

def format_hello_message(message: types.Message):
    """
    """
    message = as_list(
        Text('Hi, ', Bold(message.from_user.first_name), '!'),
        'I am a bot to help you filter emails.',
        as_marked_section(
            'I am able to manage these domains:',
            '@gmail.com',
            '@mail.ru',
            marker='- '
        ),
        'I see, you are a new user. To use my skills you need to register at service provider.',
        HashTag('#start_message'),
        sep='\n\n'
    )
    return message

@dp.message(F.text, Command('register'))
async def register_user(
        message: types.Message,
        http_session: aiohttp.ClientSession,
        auth_client: WebApplicationClient,
        redirect_uri: str
    ):
    """
    Forms a link to send a link to allow mails processing
    """
    emails_to_register = [
        message.text[entity.offset:entity.offset + entity.length] for entity in message.entities if entity.type == 'email'
    ]
    if len(emails_to_register) == 0:
        response = Text(
            'No email addresses provided to register! Send one using message schema "/register <email>" to authorize.'
        )
    elif len(emails_to_register) > 1:
        response = Text(
            'Several email addresses provided to register! Send one using message schema "/register <email>" to authorize.'
        )
    elif emails_to_register[0] in USERS_DICT:
        response = Text(
            'You have already registered this email!.'
        )
    else:
        new_user_email_domain = get_email_schema(emails_to_register[0])
        if new_user_email_domain == SupportedEmails.gmail.value:
            google_provider_cfg = await fetch(http_session, CONFIG['GOOGLE_DISCOVERY_URL'])
            google_provider_cfg = json.loads(google_provider_cfg)
            # redirect_uri
            request_uri = auth_client.prepare_request_uri(
                google_provider_cfg['authorization_endpoint'],
                redirect_uri=redirect_uri,
                scope=[
                    'openid', 'profile', 'email',
                    'https://www.googleapis.com/auth/gmail.readonly',
                    'https://www.googleapis.com/auth/gmail.metadata'
                ]
            )
            response = Text(
                'Follow ', TextLink('link', url=request_uri), ' to authorize.'
            )
            DATABASE_CONNECTION.new_user(chat_id=message.chat.id, email=emails_to_register[0], status='unverified')
            # send an email to callbacks_handler to process user registration through RabbitMQ
            PIKA_REGISTER_CHANNEL.basic_publish(
                exchange='',
                routing_key='vika_register',
                body=emails_to_register[0]
            )
        else:
            response = Text(
                f'Provided email domain is not supported: {new_user_email_domain}! Use one of these: {SUPPORTED_EMAIL_DOMAINS}'
            )
    await message.answer(
        **response.as_kwargs()
    )

@dp.message(F.text, Command('start'))
async def cmd_start(message: types.Message, bot: Bot):
    # bot неявно прокидывается в handler, можно объявить его аргументом функции, чтобы получить
    # так же можно делать с любыми переменными, передавая в диспетчер как dp['key'] = object
    # или в start_polling в качестве kwargs
    await message.answer(**format_hello_message(message).as_kwargs())

async def main() -> None:
    async with aiohttp.ClientSession() as session:
        await dp.start_polling(
            TELEGRAM_BOT, polling_timeout=30,
            http_session=session,
            auth_client=get_auth_client(),
            redirect_uri=CALLBACK_URL
        )

if __name__ == "__main__":
    try:
        DATABASE_CONNECTION = get_db(check_same_thread=False)
    except sqlite3.OperationalError:
        pass
    USERS_DICT = DATABASE_CONNECTION.get_all_users()
    PIKA_EMAILS_LOCK = Lock()
    PIKA_EMAILS_REGISTERED = set()
    PIKA_CONSUME_CHANNEL, PIKA_REGISTER_CHANNEL = init_rabbitmq_connection()
    PIKA_CONSUMER_THREAD = Thread(target=consume_pika_query, args=(PIKA_CONSUME_CHANNEL, 'vika_notify', pika_user_register_callback))
    PIKA_CONSUMER_THREAD.start()
    asyncio.run(main())
    PIKA_CONSUMER_THREAD.join()
