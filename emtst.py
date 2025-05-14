from dotenv import load_dotenv
import os

load_dotenv(override=True)  # Forces reload of existing variables
print("Email:", os.getenv("SENDER_EMAIL"))  # Should show your email