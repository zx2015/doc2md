import os
os.environ["DATABASE_URL"] = "postgresql://mock"
os.environ["REDIS_URL"] = "redis://mock"
os.environ["DOC2MD_SECRET_KEY"] = "tPzZ9YF9B2L2n_kUqG7_u1D_Q9q9U-R_WwN_e5Ww9Q0=" # 32-byte base64 fernet key

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.core.security import encrypt_key, decrypt_key

def test_encryption_roundtrip():
    original = "sk-proj-12345678"
    enc = encrypt_key(original)
    assert enc != original
    dec = decrypt_key(enc)
    assert dec == original
