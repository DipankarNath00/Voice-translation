import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from datetime import datetime
import base64
import json
from flask import current_app

# Constants
KEY_SALT = os.getenv('SECURITY_SALT', 'default-salt')  # Should be set in .env
KEY_ITERATIONS = 100000
KEY_LENGTH = 32


class SecurityManager:
    def __init__(self, app=None):
        self.app = app
        self.key = None
        self.fernet = None
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """Initialize the security manager with the Flask app"""
        self.app = app
        self.key = self._generate_key()
        self.fernet = Fernet(self.key)
        app.security_manager = self

    def _generate_key(self):
        """Generate a secure key using PBKDF2HMAC"""
        try:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=KEY_LENGTH,
                salt=KEY_SALT.encode(),
                iterations=KEY_ITERATIONS,
            )
            # Use a secure random key for production
            key = base64.urlsafe_b64encode(kdf.derive(os.urandom(32)))
            if self.app:
                self.app.logger.info("Successfully generated encryption key")
            return key
        except Exception as e:
            if self.app:
                self.app.logger.error(f"Error generating encryption key: {e}")
            raise

    def encrypt(self, data, metadata=None):
        """
        Encrypt data with optional metadata
        Args:
            data: The data to encrypt
            metadata: Optional metadata to store with encrypted data
        Returns:
            dict: Encrypted data and metadata
        """
        try:
            timestamp = datetime.utcnow().isoformat()
            encrypted_data = self.fernet.encrypt(data.encode())
            
            encrypted_info = {
                'encrypted_data': encrypted_data.decode(),
                'timestamp': timestamp,
                'metadata': metadata or {},
                'encryption_version': '1.0'
            }
            
            return encrypted_info
        except Exception as e:
            current_app.logger.error(f"Encryption error: {e}")
            raise

    def decrypt(self, encrypted_info):
        """
        Decrypt data with verification
        Args:
            encrypted_info: The encrypted data and metadata
        Returns:
            tuple: Decrypted data, metadata
        """
        try:
            encrypted_data = encrypted_info['encrypted_data'].encode()
            decrypted_data = self.fernet.decrypt(encrypted_data)
            
            return decrypted_data.decode(), encrypted_info.get('metadata', {})
        except Exception as e:
            current_app.logger.error(f"Decryption error: {e}")
            raise

    def rotate_key(self):
        """Rotate encryption key"""
        try:
            new_key = self._generate_key()
            self.key = new_key
            self.fernet = Fernet(new_key)
            current_app.logger.info("Successfully rotated encryption key")
            return True
        except Exception as e:
            current_app.logger.error(f"Key rotation error: {e}")
            return False

    def verify_key(self):
        """Verify encryption key integrity"""
        try:
            test_data = "test"
            encrypted = self.fernet.encrypt(test_data.encode())
            decrypted = self.fernet.decrypt(encrypted)
            return decrypted.decode() == test_data
        except:
            return False

# Initialize security manager
def init_app(app):
    """Initialize the security manager with the Flask app"""
    app.security_manager = SecurityManager(app)
    return app.security_manager
    app.logger.info("Security manager initialized with Fernet encryption")
