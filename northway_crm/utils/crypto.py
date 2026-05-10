import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
import hashlib


class CryptoService:
    _fernet = None
    _key = None

    @classmethod
    def _get_key(cls):
        if cls._key is None:
            secret = os.environ.get('CRM_ENCRYPTION_SECRET', 'northway-default-secret-change-in-prod')
            cls._key = hashlib.sha256(secret.encode()).digest()
        return cls._key

    @classmethod
    def encrypt(cls, plaintext: str) -> str:
        if not plaintext:
            return ''
        key = cls._get_key()
        f = Fernet(base64.urlsafe_b64encode(key))
        encrypted = f.encrypt(plaintext.encode())
        return base64.urlsafe_b64encode(encrypted).decode()

    @classmethod
    def decrypt(cls, ciphertext: str) -> str:
        if not ciphertext:
            return ''
        try:
            key = cls._get_key()
            f = Fernet(base64.urlsafe_b64encode(key))
            decrypted = f.decrypt(base64.urlsafe_b64decode(ciphertext.encode()))
            return decrypted.decode()
        except Exception as e:
            print(f"Decryption error: {e}")
            return ''

    @classmethod
    def get_last4(cls, api_key: str) -> str:
        if api_key and len(api_key) >= 4:
            return api_key[-4:]
        return ''


def encrypt_api_key(api_key: str) -> tuple:
    """Encrypts API key and returns (encrypted, last4)"""
    encrypted = CryptoService.encrypt(api_key)
    last4 = CryptoService.get_last4(api_key)
    return encrypted, last4


def decrypt_api_key(encrypted: str) -> str:
    """Decrypts API key"""
    return CryptoService.decrypt(encrypted)