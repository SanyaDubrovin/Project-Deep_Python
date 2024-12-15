import aiohttp
import json

from OpenSSL import crypto
from socket import gethostname


def consume_pika_query(channel, queue_name, callback):
    channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)
    channel.start_consuming()
    return

async def fetch(session: aiohttp.ClientSession, url: str):
    """
    Sends a HTTP request to get some content (used to collect Google auth endpoints urls)
    """
    async with session.get(url) as response:
        return await response.text()

def generate_self_signed_cert():
    # Create a key pair
    key = crypto.PKey()
    key.generate_key(crypto.TYPE_RSA, 2048)

    # Create a self-signed cert
    cert = crypto.X509()
    cert.get_subject().C = "US"
    cert.get_subject().ST = "California"
    cert.get_subject().L = "San Francisco"
    cert.get_subject().O = "My Company"
    cert.get_subject().OU = "My Organization"
    cert.get_subject().CN = gethostname()
    cert.set_serial_number(1000)
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(10*365*24*60*60)
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(key)
    cert.sign(key, 'sha256')

    # Save the key and cert to files
    with open("key.pem", "wb") as key_file:
        key_file.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, key))
    with open("cert.pem", "wb") as cert_file:
        cert_file.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))

def encode_message(python_object):
    if not isinstance(python_object, str):
        python_object = json.dumps(python_object)
    return python_object.encode()

def decode_message(python_object):
    return json.loads(python_object.decode())
