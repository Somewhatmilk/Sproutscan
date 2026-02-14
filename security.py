# --- START OF FILE security.py ---
import os
from cryptography.fernet import Fernet

class SecurityManager:
    def __init__(self):
        # In production, load this from an .env file or a secure vault
        # For this demo, we check if a key file exists, otherwise generate one
        self.key_file = 'secret.key'
        self.key = self.load_key()
        self.cipher = Fernet(self.key)

    def load_key(self):
        if os.path.exists(self.key_file):
            with open(self.key_file, 'rb') as key_file:
                return key_file.read()
        else:
            key = Fernet.generate_key()
            with open(self.key_file, 'wb') as key_file:
                key_file.write(key)
            return key

    def encrypt_data(self, data):
        """Encrypts a string and returns bytes"""
        if not data: return None
        return self.cipher.encrypt(data.encode()).decode()

    def decrypt_data(self, encrypted_data):
        """Decrypts bytes/string back to string"""
        if not encrypted_data: return ""
        try:
            return self.cipher.decrypt(encrypted_data.encode()).decode()
        except Exception:
            return "[Encrypted Data Error]"

# Initialize the manager
sec = SecurityManager()