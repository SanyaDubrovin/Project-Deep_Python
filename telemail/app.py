import uvicorn
import asyncio
import pika

from multiprocessing import Process
from threading import Thread, Lock

from bot import start_bot, run_tg_msg_sender
from utils import decode_message, encode_message
from callbacks_handler import app, publish_callback_message_loop
from db import get_db


UPDATED_TEMP_TABLES_FLAG_LOCK = Lock()
UPDATED_TEMP_TABLES_FLAG = 0
RUN_REGISTER_FLAG = 0

def google_user_info_callback(
        ch, method, properties, body,
        db_conn=get_db()
    ):
    message = decode_message(body)
    db_conn.insert_google_user_temp(
        google_unique_id=message['google_unique_id'],
        email=message['email'],
        username=message['username'],
        verified=message['verified'],
        id_token=message['id_token'],
        access_token=message['access_token'],
        token_type=message['token_type'],
        scope=message['scope'],
        expires_in=message['expires_in'],
        token_register_datetime=message['token_register_datetime']
    )
    with UPDATED_TEMP_TABLES_FLAG_LOCK:
        UPDATED_TEMP_TABLES_FLAG = 1
    return

def tg_user_info_callback(
        ch, method, properties, body,
        db_conn=get_db()
    ):
    message = decode_message(body)
    db_conn.insert_tg_user_temp(
        chat_id=message['chat_id'],
        email=message['email']
    )
    with UPDATED_TEMP_TABLES_FLAG_LOCK:
        UPDATED_TEMP_TABLES_FLAG = 1
    return

def run_messages_consumer():
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    consume_channel = connection.channel()
    consume_channel.queue_declare(queue='vika_register')
    consume_channel.queue_declare(queue='vika_callbacks')
    consume_channel.basic_consume(
        queue='vika_register',
        on_message_callback=tg_user_info_callback,
        auto_ack=True
    )
    consume_channel.basic_consume(
        queue='vika_callbacks',
        on_message_callback=google_user_info_callback,
        auto_ack=True
    )
    consume_channel.start_consuming()
    return

def mail_loop():
    while True:
        pass

def run_app():
    threads = [
        Thread(target=run_messages_consumer),
        Thread()
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return


def run_bot_process():
    threads = [
        Thread(target=start_bot),
        Thread(target=run_tg_msg_sender)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return

def run_callbacks_process(app, host, port, ssl_keyfile, ssl_certfile):
    publish_loop = asyncio.new_event_loop()
    publish_thread = Thread(target=publish_callback_message_loop, args=(publish_loop,))
    publish_thread.start()
    
    app.state.publish_loop = publish_loop
    uvicorn.run(app, host=host, port=port, ssl_keyfile=ssl_keyfile, ssl_certfile=ssl_certfile)
    
    publish_thread.join()
    return

if __name__ == '__main__':
    processes = [
        Process(target=run_bot_process),
        Process(target=run_callbacks_process, args=(app,), kwargs={'host': '0.0.0.0', 'port': 5000, 'ssl_keyfile': 'key.pem', 'ssl_certfile': 'cert.pem'}),

    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join()
