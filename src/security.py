import hashlib
import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

class SecurityManager:
    def __init__(self):
        self._key = self._generate_key() 
        self._cipher = Fernet(self._key)

    def _generate_key(self):
        password = b"WilowLocalSecureKey"
        salt = b'static_salt_change_in_prod' 
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password))

    def encrypt_data(self, data: str) -> bytes:
        if not data: return b""
        return self._cipher.encrypt(data.encode())

    def decrypt_data(self, token: bytes) -> str:
        if not token: return ""
        try:
            return self._cipher.decrypt(token).decode()
        except Exception:
            return "[DECRYPTION_FAILED]"

    @staticmethod
    def get_file_hash(file_path):
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        return sha256.hexdigest()

    @staticmethod
    def sanitize_input(text):
        if text and str(text).startswith(('=', '+', '-', '@')):
            return f"'{text}"
        return text