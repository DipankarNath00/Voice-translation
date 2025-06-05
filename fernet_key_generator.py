from cryptography.fernet import Fernet

def generate_key():
    key = Fernet.generate_key()
    print("\n=== Fernet Key Generator ===")
    print("\nYour Fernet key:", key.decode())
    print("\nInstructions:")
    print("1. Save this key securely")
    print("2. Set it as an environment variable:")
    print("   Windows: set FERNET_KEY=your_key_here")
    print("   Linux/Mac: export FERNET_KEY=your_key_here")
    print("3. Use this key in Military Mode")
    print("\nWARNING: Keep this key secure and never share it!")
    print("===========================\n")

if __name__ == "__main__":
    generate_key() 