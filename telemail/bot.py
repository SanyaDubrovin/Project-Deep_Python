import asyncio
from enum import Enum
import json
import logging
import re
from threading import Lock, Thread

from aiogram import Bot, Dispatcher, html, types
from aiogram import F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters.command import Command
from aiogram.utils.formatting import (
    Bold,
    HashTag,
    Text,
    TextLink,
    as_list,
    as_marked_section,
)
import aiohttp
from dotenv import dotenv_values
from oauthlib.oauth2 import WebApplicationClient
import pika

from utils import decode_message, encode_message, fetch


EMAIL_REGEX = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'

logging.basicConfig(level=logging.INFO)
CONFIG = dotenv_values()
CALLBACK_URL = CONFIG.get('CALLBACK_URL', None)
SUPPORTED_EMAIL_DOMAINS = {'gmail',}
class SupportedEmails(Enum):
    gmail = 'gmail.com'

dp = Dispatcher()



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
        'I am a bot to help you filter emails.' + str(message.chat.id),
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
        redirect_uri: str,
        pika_channel
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
                    # Не использовать! Не даёт получать полные сообщения
                    # 'https://www.googleapis.com/auth/gmail.metadata'
                ]
            )
            response = Text(
                'Follow ', TextLink('link', url=request_uri), ' to authorize.'
            )
            # send an email to callbacks_handler to process user registration through RabbitMQ
            register_message = {
                'type': 'tg_temp',
                'email': emails_to_register[0],
                'chat_id': message.chat.id
            }
            register_message = encode_message(register_message)
            pika_channel.basic_publish(
                exchange='',
                routing_key='vika_register',
                body=register_message
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

async def run_tg_poller(publish_channel) -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    async with aiohttp.ClientSession() as session:
        bot = Bot(
            default=DefaultBotProperties(
                parse_mode=ParseMode.HTML
            ),
            token=CONFIG['TOKEN'],
            #session=session
        )
        await dp.start_polling(
            bot, polling_timeout=30,
            handle_signals=False,
            http_session=session,
            auth_client=get_auth_client(),
            redirect_uri=CALLBACK_URL,
            pika_channel=publish_channel
        )
    return


async def message_callback(bot, message, chat_id_to_send):
    try:
        await bot.send_message(chat_id_to_send, message)
    except Exception as exc:
        print('Error while sending a message:', exc)

async def run_consumers(bot, chat_id_to_send):
    loop = asyncio.get_event_loop()
    def on_message(ch, method, properties, body):
        try:
            message = decode_message(body)
        except Exception:
            print('Error while decoding a message:', exc)
            return
        future = asyncio.run_coroutine_threadsafe(message_callback(bot, message['text'], message['chat_id']), loop)
        return future.result()
    
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    consume_channel = connection.channel()
    consume_channel.queue_declare(queue='messages_to_tg')
    consume_channel.basic_consume(queue='messages_to_tg', on_message_callback=on_message, auto_ack=True)
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, consume_channel.start_consuming)
    except Exception as exc:
        print('Error while consuming', exc)
    finally:
        connection.close()

def run_tg_msg_sender():
    chat_id_to_send = 1001182656
    bot = Bot(
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML
        ),
        token=CONFIG['TOKEN']
    )
    asyncio.run(run_consumers(bot, chat_id_to_send))
    # try:
    #     bot.session.close()
    # except:
    #     pass
    return

def start_bot():
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    register_publish_channel = connection.channel()
    register_publish_channel.queue_declare(queue='vika_register')

    asyncio.run(run_tg_poller(register_publish_channel))
    return


if __name__ == "__main__":
    threads = [
        Thread(target=start_bot),
        Thread(target=run_tg_msg_sender)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
