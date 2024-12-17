import psycopg2

from dotenv import dotenv_values


def get_db(
        database: str,
        user: str,
        password: str,
        host: str,
        port: int,
        init_tables=True
    ):
    config = dotenv_values('.env')
    return TelemailDB(
        database=config['DATABASE_NAME'],
        user=config['DATABASE_USERNAME'],
        password=config['DATABASE_USER_PASSWORD'],
        host=config['DATABASE_HOST'],
        port=config['DATABASE_PORT'],
        init_tables=True
    )

class TelemailDB(object):
    def __init__(
            self,
            database: str,
            user: str,
            password: str,
            host: str,
            port: int,
            init_tables=True
        ):
        self.database = database
        self.user = user
        self.password = password
        self.host = host
        self.port = port
        self.connection = self.connect()
        if init_tables:
            self.initialise_tables()

    def connect(self):
        return psycopg2.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database
        )

    def initialise_tables(self):
        if self.connection is None:
            raise TypeError('Connect to database before initialising tables!')
        with self.connection.cursor() as cursor:
            cursor.execute("""
                CREATE TEMPORARY TABLE IF NOT EXISTS telemail_tg_register_temp (
                    chat_id VARCHAR(32), email VARCHAR(128)
                )
            """)
            cursor.execute("""
                CREATE TEMPORARY TABLE IF NOT EXISTS google_user_info_temp (
                    google_unique_id VARCHAR(32),
                    email VARCHAR(128) NOT NULL,
                    username VARCHAR(128),
                    verified BOOLEAN,
                    id_token VARCHAR(2048),
                    access_token VARCHAR(256),
                    token_type VARCHAR(16),
                    scope VARCHAR(256),
                    expires_in INT,
                    token_register_datetime DATETIME
                )
            """)
            # token_type # str (value: 'Bearer')
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS telemail_users (
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
                    token_register_datetime DATETIME
                )
            """)
            cursor.execute("""
                CREATE INDEX email_index ON telemail_users USING btree (email);
            """)

    def insert_tg_user_temp(self, chat_id: str, email: str):
        with self.connection.cursor() as cursor:
            cursor.execute("""
                    INSERT INTO telemail_tg_register_temp (chat_id, email) VALUES (%s, %s)
                """,
                (chat_id, email)
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
            email_poll_period=60
        ):
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
                    token_register_datetime
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                    token_register_datetime
                )
            )

    def get_tg_temp_users(self):
        with self.connection.cursor() as cursor:
            cursor.execute('SELECT * FROM telemail_tg_register_temp')
            return cursor.fetchall()
    
    def get_google_temp_users(self):
        with self.connection.cursor() as cursor:
            cursor.execute('SELECT * FROM google_user_info_temp')
            return cursor.fetchall()

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
                    INSERT INTO telemail_users (
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

    def get_registered_users(self):
        with self.connection.cursor() as cursor:
            cursor.execute('SELECT * FROM telemail_users')
            return cursor.fetchall()
