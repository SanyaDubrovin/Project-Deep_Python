import sqlite3

from typing import Optional


USERS_DB_NAME = 'db.sqlite'

class TelegramUsers(object):
    def __init__(self, db_path: str, **kwargs):
        self.conn = sqlite3.connect(db_path, **kwargs)
        self.create_user_table()

    def create_user_table(self):
        with self.conn:
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT,
                    email TEXT UNIQUE,
                    chat_id TEXT,
                    status TEXT
                )
            ''')

    def new_user(self, username: str='', email: str='', chat_id: str='', status: str = 'unverified'):
        try:
            with self.conn:
                self.conn.execute('''
                    INSERT INTO users (username, email, chat_id, status) VALUES (?, ?, ?, ?)
                ''', (username, email, chat_id, status))
            return True
        except sqlite3.IntegrityError:
            return False

    def update_user_info_by_email(
                self, email: str,
                username: Optional[str]=None,
                chat_id: Optional[str]=None,
                status: Optional[str]=None
            ):
        fields_to_update = {
            'username': username,
            'chat_id': chat_id,
            'status': status
        }
        updating_field_names = {key:fields_to_update[key] for key in fields_to_update if fields_to_update[key] is not None}
        if len(updating_field_names) == 0:
            return True
        set_rows = []
        values_to_update = []
        for key in updating_field_names:
            set_rows.append(f'{key} = ?')
            values_to_update.append(updating_field_names[key])
        values_to_update.append(email)
        try:
            with self.conn:
                self.conn.execute(
                    f'''
                        UPDATE users SET {', '.join(set_rows)} WHERE email = ?
                    ''', values_to_update)
            return True
        except sqlite3.IntegrityError:
            pass
        return False

    def get_all_users(self, dict_view=True):
        with self.conn:
            users = self.conn.execute('SELECT * FROM users').fetchall()
        if dict_view:
            users = {user[2]: {'id':user[0], 'username': user[1], 'chat_id': user[3], 'status': user[4]} for user in users}
        return users

    def get_user_by_email(self, email, dict_view=True):
        with self.conn:
            user = self.conn.execute(f'SELECT * FROM users WHERE email = \'{email}\'').fetchall()
        if dict_view:
            user = {user[0][2]: {'id':user[0][0], 'username': user[0][1], 'chat_id': user[0][3], 'status': user[0][4]}}
        return user

def get_db(db_name: str=USERS_DB_NAME, **kwargs):
    return TelegramUsers(db_name, **kwargs)
