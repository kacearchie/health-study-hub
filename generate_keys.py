import secrets
import base64
import os

def generate_keys():
    print("=" * 50)
    print("🔑 GENERATE YOUR SECURE KEYS")
    print("=" * 50)
    
    # Generate Flask Secret Key (32 bytes = 64 hex characters)
    flask_secret = secrets.token_hex(32)
    print("\n📌 FLASK SECRET KEY (for sessions and CSRF):")
    print(f"SECRET_KEY={flask_secret}")
    
    # Generate JWT Secret Key (32 bytes = 64 hex characters)
    jwt_secret = secrets.token_hex(32)
    print("\n📌 JWT SECRET KEY (for authentication tokens):")
    print(f"JWT_SECRET_KEY={jwt_secret}")
    
    # Generate alternative key (base64 encoded)
    alt_key = base64.b64encode(os.urandom(32)).decode('utf-8')
    print("\n📌 ALTERNATIVE KEY (base64 format):")
    print(f"ALTERNATIVE_KEY={alt_key}")
    
    # Generate a simple password for testing
    simple_key = secrets.token_urlsafe(32)
    print("\n📌 SIMPLE KEY (URL-safe):")
    print(f"SIMPLE_KEY={simple_key}")
    
    print("\n" + "=" * 50)
    print("📝 Copy these to your .env file:")
    print("=" * 50)
    print(f"""
SECRET_KEY={flask_secret}
JWT_SECRET_KEY={jwt_secret}
OPENAI_API_KEY=sk-your-openai-key-here
    """)

if __name__ == "__main__":
    generate_keys()