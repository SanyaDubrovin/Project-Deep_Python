import uvicorn
import asyncio

from multiprocessing import Process
from threading import Thread, Lock

from bot import start_bot, run_tg_msg_sender
from callbacks_handler import app, publish_callback_message_loop


UPDATE_EMAILS_FLAG_LOCK = Lock()
UPDATE_EMAILS_FLAG = 0

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
