from cryptography.fernet import Fernet
import hashlib
import base64
from app.core.config import settings

_derived_key = base64.urlsafe_b64encode(hashlib.sha256(settings.DOC2MD_SECRET_KEY.encode()).digest())
_fernet = Fernet(_derived_key)

def encrypt_key(plain_key: str) -> str:
    if not plain_key:
        return ""
    return _fernet.encrypt(plain_key.encode()).decode()

def decrypt_key(encrypted_key: str) -> str:
    if not encrypted_key:
        return ""
    return _fernet.decrypt(encrypted_key.encode()).decode()
