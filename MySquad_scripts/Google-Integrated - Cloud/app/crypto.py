"""
Responsibility: Manage token encryption and decryption.
Provides symmetric encryption (Fernet) for securely storing user refresh tokens
in the database. Uses environment variable TOKEN_ENCRYPTION_KEY for cipher initialization.
"""

import os
from cryptography.fernet import Fernet

# Load encryption key from environment
FERNET_KEY = os.getenv("TOKEN_ENCRYPTION_KEY")

if not FERNET_KEY:
    raise RuntimeError(
        "TOKEN_ENCRYPTION_KEY environment variable is required. "
        "Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
    )

# Initialize Fernet cipher
fernet = Fernet(FERNET_KEY.encode())


def encrypt_token(token: str) -> bytes:
    """
    Encrypt a plaintext token using Fernet symmetric encryption.
    
    Args:
        token: Plaintext token (e.g., refresh token)
        
    Returns:
        Encrypted bytes
        
    Raises:
        ValueError: If token is empty
    """
    if not token:
        raise ValueError("Token cannot be empty")
    return fernet.encrypt(token.encode())


def decrypt_token(encrypted_token: bytes) -> str:
    """
    Decrypt an encrypted token back to plaintext.
    
    Args:
        encrypted_token: Encrypted token bytes
        
    Returns:
        Decrypted plaintext token
        
    Raises:
        ValueError: If token is empty or invalid
    """
    if not encrypted_token:
        raise ValueError("Encrypted token cannot be empty")
    return fernet.decrypt(encrypted_token).decode()
