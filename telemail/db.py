import psycopg2
import datetime

from typing import Optional
from dotenv import dotenv_values


def get_db(init_tables=False):
    config = dotenv_values('.env')
    return TelemailDB(
        database=config['DATABASE_NAME'],
        user=config['DATABASE_USERNAME'],
        #password=config['DATABASE_USER_PASSWORD'],
        #host=config['DATABASE_HOST'],
        #port=config['DATABASE_PORT'],
        init_tables=init_tables
    )

class TelemailDB(object):
    def __init__(
            self,
            database: str,
            user: str,
            password: Optional[str]=None,
            host: Optional[str]=None,
            port: Optional[int]=None,
            init_tables=False
        ):
        print('creating')
        self.connection_params = {
            'database': database,
            'user': user,
            'password': password,
            'host': host,
            'port': port
        }
        self.connection = self.connect()
        print('Connected')
        if init_tables:
            self.initialise_tables()

    def connect(self):
        connection_params = {
            key: self.connection_params[key] for key in self.connection_params if self.connection_params[key] is not None
        }
        try:
            return psycopg2.connect(**connection_params)
        except psycopg2.OperationalError:
            raise Exception('Error while getting a connection object to postgresql!')
    
    def close(self):
        if self.connection is not None:
            self.connection.close()
    
    def commit(self):
        if self.connection is not None:
            self.connection.commit()

    def initialise_tables(self):
        if self.connection is None:
            raise TypeError('Connect to database before initialising tables!')
        print('creating')
        with self.connection.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS telemail_tg_register_temp (
                    chat_id VARCHAR(32), email VARCHAR(128), record_datetime TIMESTAMP
                )
            """)
            print('1')
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS google_user_info_temp (
                    google_unique_id VARCHAR(32),
                    email VARCHAR(128) NOT NULL,
                    email_poll_period SMALLINT,
                    username VARCHAR(128),
                    verified BOOLEAN,
                    id_token VARCHAR(2048),
                    access_token VARCHAR(256),
                    token_type VARCHAR(16),
                    scope VARCHAR(256),
                    expires_in INT,
                    token_register_datetime TIMESTAMP,
                    record_datetime TIMESTAMP
                )
            """)
            print('2')
            # token_type # str (value: 'Bearer')
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS telemail_reg_users (
                    chat_id VARCHAR(32) NOT NULL,
                    google_unique_id VARCHAR(32),
                    email VARCHAR(128) NOT NULL,
                    email_poll_period SMALLINT,
                    username VARCHAR(128),
                    verified BOOLEAN,
                    id_token VARCHAR(2048),
                    access_token VARCHAR(256),
                    token_type VARCHAR(16),
                    scope VARCHAR(256),
                    expires_in INT,
                    token_register_datetime TIMESTAMP
                )
            """)
            print('3')
            # cursor.execute("""
                # CREATE INDEX email_index ON telemail_reg_users USING btree (email);
            # """)
            # print('finished')
        self.connection.commit()

    def insert_tg_user_temp(self, chat_id: str, email: str, record_datetime=None):
        if record_datetime is None:
            record_datetime = datetime.datetime.now().isoformat()
        with self.connection.cursor() as cursor:
            cursor.execute("""
                    INSERT INTO telemail_tg_register_temp (
                        chat_id, email, record_datetime
                    ) VALUES (%s, %s, %s)
                """,
                (chat_id, email, record_datetime)
            )
    
    def insert_google_user_temp(self,
            google_unique_id,
            email,
            username,
            verified,
            id_token,
            access_token,
            token_type,
            scope,
            expires_in,
            token_register_datetime,
            email_poll_period=60,
            record_datetime=None
        ):
        if record_datetime is None:
            record_datetime = datetime.datetime.now().isoformat()
        with self.connection.cursor() as cursor:
            cursor.execute("""INSERT INTO google_user_info_temp (
                    google_unique_id,
                    email,
                    email_poll_period,
                    username,
                    verified,
                    id_token,
                    access_token,
                    token_type,
                    scope,
                    expires_in,
                    token_register_datetime,
                    record_datetime
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                    google_unique_id,
                    email,
                    email_poll_period,
                    username,
                    verified,
                    id_token,
                    access_token,
                    token_type,
                    scope,
                    expires_in,
                    token_register_datetime,
                    record_datetime
                )
            )

    def get_tg_temp_users(self, to_dict=True):
        with self.connection.cursor() as cursor:
            cursor.execute('SELECT * FROM telemail_tg_register_temp')
            columns = cursor.description
            rows = cursor.fetchall()
            if to_dict:
                return {column.name: [row[column_num] for row in rows] for column_num, column in enumerate(columns)}
            return rows
    
    def get_google_temp_users(self, to_dict=True):
        with self.connection.cursor() as cursor:
            cursor.execute('SELECT * FROM google_user_info_temp')
            columns = cursor.description
            rows = cursor.fetchall()
            if to_dict:
                return {column.name: [row[column_num] for row in rows] for column_num, column in enumerate(columns)}
            return rows

    def insert_new_user(
                self,
                chat_id,
                google_unique_id,
                email,
                username,
                verified,
                id_token,
                access_token,
                token_type,
                scope,
                expires_in,
                token_register_datetime,
                email_poll_period=60
            ):
        with self.connection.cursor() as cursor:
            cursor.execute("""
                    INSERT INTO telemail_reg_users (
                        chat_id,
                        google_unique_id,
                        email,
                        email_poll_period,
                        username,
                        verified,
                        id_token,
                        access_token,
                        token_type,
                        scope,
                        expires_in,
                        token_register_datetime
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    chat_id,
                    google_unique_id,
                    email,
                    email_poll_period,
                    username,
                    verified,
                    id_token,
                    access_token,
                    token_type,
                    scope,
                    expires_in,
                    token_register_datetime
                )
            )
        return

    def get_registered_users(self, to_dict=True):
        with self.connection.cursor() as cursor:
            cursor.execute('SELECT * FROM telemail_reg_users')
            columns = cursor.description
            rows = cursor.fetchall()
            if to_dict:
                return {
                    column.name: [row[column_num] for row in rows] for column_num, column in enumerate(columns)
                }
            return rows
