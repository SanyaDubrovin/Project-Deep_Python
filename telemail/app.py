import uvicorn
import asyncio
import pika
import pandas as pd
import logging
import requests
from time import time, sleep

from copy import copy
from multiprocessing import Process, Value
from threading import Thread, Lock

from bot import start_bot, run_tg_msg_sender
from utils import decode_message, encode_message
from callbacks_handler import app, publish_callback_message_loop
from db import get_db


logging.basicConfig(loglevel=logging.INFO)

def google_user_info_callback(
        ch, method, properties, body,
        db_conn=get_db(), **kwargs
    ):
    message = decode_message(body)
    print(message)
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
    db_conn.commit()
    kwargs['UPDATED_TEMP_TABLES_FLAG'].value = 1
    return

def tg_user_info_callback(
        ch, method, properties, body,
        db_conn=get_db(), **kwargs
    ):
    message = decode_message(body)
    print(message)
    db_conn.insert_tg_user_temp(
        chat_id=message['chat_id'],
        email=message['email']
    )
    db_conn.commit()
    kwargs['UPDATED_TEMP_TABLES_FLAG'].value = 1
    return

def run_messages_consumer(**kwargs):
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    consume_channel = connection.channel()
    consume_channel.queue_declare(queue='vika_register')
    consume_channel.queue_declare(queue='vika_callbacks')
    
    UPDATED_TEMP_TABLES_FLAG = kwargs['UPDATED_TEMP_TABLES_FLAG']
    def set_param_to_callback(func):
        def wrapper(*args, **kwargs):
            return func(
                *args,
                UPDATED_TEMP_TABLES_FLAG=UPDATED_TEMP_TABLES_FLAG,
                **kwargs
            )
        return wrapper
    consume_channel.basic_consume(
        queue='vika_register',
        on_message_callback=set_param_to_callback(tg_user_info_callback),
        auto_ack=True
    )
    consume_channel.basic_consume(
        queue='vika_callbacks',
        on_message_callback=set_param_to_callback(google_user_info_callback),
        auto_ack=True
    )
    consume_channel.start_consuming()
    return

def update_poll_time(
        users_next_poll_period, last_poll_time, email_to_user_info,
        DEFAULT_SLEEP_TIME=5
    ):
    users_to_poll = []
    for user_num, user in enumerate(users_next_poll_period):
        until_poll_prev = users_next_poll_period[user_num][1]
        since_last_poll_time = time() - last_poll_time
        until_poll_next = until_poll_prev - since_last_poll_time
        if until_poll_next - 1e-4 < 0:
            until_poll_next = email_to_user_info[user[0]].get('email_poll_period', DEFAULT_SLEEP_TIME)
            users_to_poll.append(user[0])
        users_next_poll_period[user_num][1] = until_poll_next
    return users_to_poll

def init_tg_send_messages_queue(func):
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    tg_msgs_channel = connection.channel()
    tg_msgs_channel.queue_declare(queue='messages_to_tg')
    def send_msg_func(*args, **kwargs):
        return func(*args, publish_channel=tg_msgs_channel, **kwargs)
    return send_msg_func

def send_mails_to_user(message_text: str, chat_id: int, publish_channel):
    message = {
        'text': message_text,
        'chat_id': chat_id
    }
    message = encode_message(message)
    publish_channel.basic_publish(
        exchange='',
        routing_key='messages_to_tg',
        body=message
    )

def request_user_mail_list(email, user_id, access_token, emails_limit=10):
    """
    {'error': {'code': 403, 'message': "Metadata scope doesn't allow format FULL", 'errors': [{'message': "Metadata scope doesn't allow format FULL", 'domain': 'global', 'reason': 'forbidden'}], 'status': 'PERMISSION_DENIED'}}
    """
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    params = {
        'maxResults': emails_limit,
        'format': 'full'
    }
    list_msgs_req = f'https://gmail.googleapis.com/gmail/v1/users/{email}/messages'
    print(list_msgs_req)
    response = requests.get(
        list_msgs_req,
        headers=headers
    )
    messages = response.json().get('messages', [])
    print(messages)

    # Print the email addresses
    # Write messages parsing
    for message in messages:
        msg_response = requests.get(
            f'https://gmail.googleapis.com/gmail/v1/users/{email}/messages/{message["id"]}',
            headers=headers,
            params=params
        )
        msg = msg_response.json()
        print(msg)
        headers = msg['payload']['headers']
        for header in headers:
            print(header)
            if header['name'] == 'From':
                print(header['value'])

def poll_user_emails(users_to_poll, email_to_user_info):
    for email in users_to_poll:
        print('Polling an email:', email)
        mails = request_user_mail_list(
            email, email_to_user_info[email]['google_unique_id'],
            email_to_user_info[email]['access_token']
        )
        print(mails)

def users_info_to_email_dict(users_info):
    print(users_info)
    return {
        email: {
            'chat_id': chat_id,
            'google_unique_id': google_unique_id,
            'email_poll_period': email_poll_period,
            'username': username,
            'verified': verified,
            'id_token': id_token,
            'access_token': access_token,
            'token_type': token_type,
            'scope': scope,
            'expires_in': expires_in,
            'token_register_datetime': token_register_datetime
        } for email, chat_id, google_unique_id, google_unique_id, email_poll_period, username, verified, id_token, access_token, token_type, scope, expires_in, token_register_datetime \
            in zip(
                users_info['email'], users_info['chat_id'], users_info['google_unique_id'], users_info['google_unique_id'],
                users_info['email_poll_period'], users_info['username'], users_info['verified'], users_info['id_token'],
                users_info['access_token'], users_info['token_type'], users_info['scope'], users_info['expires_in'],
                users_info['token_register_datetime']
            )
    }

def register_new_users(email_to_user_info: dict, db_conn=get_db()) -> dict:
    tg_users = pd.DataFrame(db_conn.get_google_temp_users())
    google_user_dfs = pd.DataFrame(db_conn.get_tg_temp_users())
    tg_users.drop(labels=['record_datetime'], axis=1, inplace=True)
    google_user_dfs.drop(labels=['record_datetime'], axis=1, inplace=True)
    new_users = pd.merge(
        left=google_user_dfs, right=tg_users, on='email', how='inner'
    )
    if len(new_users) == 0:
        return email_to_user_info
    for new_user in new_users.to_dict(orient='records'):
        print(new_users)
        # check that such user exists
        if new_user['email'] in email_to_user_info:
            raise ValueError(f'User with email {new_user["email"]} already exists!')
        try:
            print(new_user)
            db_conn.insert_new_user(**new_user)
            db_conn.commit()
            print('New user registered!')
            new_user_email = new_user.pop('email')
            email_to_user_info[new_user_email] = new_user
        except Exception as exc:
            print('Faced error while inserting a record', new_user, 'Exception:', exc)
    
    # !
    # update email_to_user_info with new users
    # !
    return email_to_user_info

def mail_loop(db_conn=get_db(), **kwargs):
    """
    Trouble: after registering does not poll new user
    """
    users = db_conn.get_registered_users()
    email_to_user_info = users_info_to_email_dict(users)
    users_df = pd.DataFrame(users)
    until_users_poll_time = [
        [email, email_poll_period] for email, email_poll_period in zip(
            users['email'], users['email_poll_period']
        )
    ]
    until_users_poll_time = sorted(until_users_poll_time, key=lambda x: x[1])
    until_next_poll_time = min(
        until_users_poll_time[0][1], kwargs['DEFAULT_SLEEP_TIME'].value
        ) if len(until_users_poll_time) > 0 else kwargs['DEFAULT_SLEEP_TIME'].value
    last_poll_time = time()
    while True:
        print('New polling circle:', email_to_user_info)
        sleep(until_next_poll_time)
        current_users_to_poll = update_poll_time(
            until_users_poll_time, last_poll_time, email_to_user_info,
            DEFAULT_SLEEP_TIME=kwargs['DEFAULT_SLEEP_TIME'].value
        )
        # create a thread for this task?
        poll_user_emails(current_users_to_poll, email_to_user_info)
        print(kwargs['UPDATED_TEMP_TABLES_FLAG'].value)
        if kwargs['UPDATED_TEMP_TABLES_FLAG'].value:
            email_to_user_info = register_new_users(email_to_user_info)
            kwargs['UPDATED_TEMP_TABLES_FLAG'].value = 0


def run_app():
    UPDATED_TEMP_TABLES_FLAG_LOCK = Lock()
    kwargs = {
        'UPDATED_TEMP_TABLES_FLAG': Value('I', 0, lock=False),
        'RUN_REGISTER_FLAG': Value('I', 0, lock=False),
        'DEFAULT_SLEEP_TIME': Value('I', 5, lock=False)
    }
    threads = [
        Thread(target=run_messages_consumer, kwargs=kwargs),
        Thread(target=mail_loop, kwargs=kwargs)
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
    conn = get_db(init_tables=True)
    conn.commit()
    conn.close()
    print('Start procs')
    processes = [
        Process(target=run_bot_process),
        Process(
            target=run_callbacks_process, args=(app,), kwargs={
                'host': '0.0.0.0', 'port': 5000, 'ssl_keyfile': 'key.pem', 'ssl_certfile': 'cert.pem'
            }
        ),
        Process(target=run_app)
    ]
    for process in processes:
        process.start()
    print('Procs started')
    for process in processes:
        process.join()
