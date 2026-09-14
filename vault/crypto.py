import hashlib, hmac, json, os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings

def seal(data, context):
    nonce = os.urandom(12)
    return nonce + AESGCM(settings.MASTER_KEY).encrypt(nonce, data, context.encode())
def unseal(data, context):
    data = bytes(data)
    return AESGCM(settings.MASTER_KEY).decrypt(data[:12],data[12:],context.encode())
def pack(obj, context): return seal(json.dumps(obj,ensure_ascii=False,default=str).encode(),context)
def unpack(data, context): return json.loads(unseal(data,context))
def blind(value):
    return hmac.new(settings.INDEX_KEY,value.encode(),hashlib.sha256).hexdigest()
