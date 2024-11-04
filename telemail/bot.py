import asyncio
import aiohttp
import logging
import json

from dotenv import dotenv_values
from oauthlib.oauth2 import WebApplicationClient

from aiogram import Bot, Dispatcher, types, html
from aiogram.filters.command import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.formatting import as_list, as_marked_section, Text, Bold, HashTag, TextLink
from aiogram.enums import ParseMode
from aiogram import F


logging.basicConfig(level=logging.INFO)
CONFIG = dotenv_values()
dp = Dispatcher()

def get_auth_client():
    return WebApplicationClient(CONFIG['GOOGLE_CLIENT_ID'])

def get_provider_cfg():
    """
    Returns 
    """

def get_login_redirect_link(auth_client):
    """
    """

async def pika_poller():
    """
    """

def format_mail_message():
    """
    """

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

async def fetch(session: aiohttp.ClientSession, url: str):
    async with session.get(url) as response:
        return await response.text()

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
    await message.answer(
        **response.as_kwargs()
    )

@dp.message(F.text, Command('start'))
async def cmd_start(message: types.Message, bot: Bot):
    await message.answer(**format_hello_message(message).as_kwargs())

async def main() -> None:
    async with aiohttp.ClientSession() as session:
        bot = Bot(
            default=DefaultBotProperties(
                parse_mode=ParseMode.HTML
            ),
            token=CONFIG['TOKEN']
        )
        await dp.start_polling(
            bot, polling_timeout=30,
            http_session=session,
            auth_client=get_auth_client(),
            redirect_uri='https://tlm.tmhu.space/login/callback'
        )

if __name__ == "__main__":
    asyncio.run(main())

