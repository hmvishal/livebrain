import os
from dotenv import load_dotenv

# Load environment variables from config.env file
# We specify the path because the script is in src/ and the config.env is in the root.
from pathlib import Path
dotenv_path = Path(__file__).parent.parent / 'config.env'
load_dotenv(dotenv_path=dotenv_path)

# Telegram Bot Token
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Instamojo API credentials
INSTAMOJO_API_KEY = os.getenv("INSTAMOJO_API_KEY")
INSTAMOJO_AUTH_TOKEN = os.getenv("INSTAMOJO_AUTH_TOKEN")

# Admin's Telegram ID
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")

from instamojo_wrapper import Instamojo

# Instamojo API client
# Use the test environment if the API key is a placeholder
if INSTAMOJO_API_KEY == "YOUR_INSTAMOJO_API_KEY":
    INSTAMOJO_API = Instamojo(
        api_key="test",
        auth_token="test",
        endpoint='https://test.instamojo.com/api/1.1/'
    )
else:
    INSTAMOJO_API = Instamojo(
        api_key=INSTAMOJO_API_KEY,
        auth_token=INSTAMOJO_AUTH_TOKEN
    )

import google.generativeai as genai

# Gemini AI Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY and GEMINI_API_KEY != "YOUR_GEMINI_API_KEY":
    genai.configure(api_key=GEMINI_API_KEY)
    GEMINI_MODEL = genai.GenerativeModel('gemini-2.0-flash')
else:
    GEMINI_MODEL = None

# Check if all required environment variables are set
if not all([TELEGRAM_BOT_TOKEN, ADMIN_TELEGRAM_ID]):
    raise ValueError("TELEGRAM_BOT_TOKEN and ADMIN_TELEGRAM_ID must be set in your config.env file.")
