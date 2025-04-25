from cryptography.fernet import Fernet

key = Fernet.generate_key()
print("Your Fernet key:", key.decode())
