import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
EBAY_APP_ID       = os.getenv("EBAY_APP_ID", "")
EBAY_CERT_ID      = os.getenv("EBAY_CERT_ID", "")
MODEL_NAME        = "claude-opus-4-5"
MAX_MEMORY_MSG    = 20
LOG_LEVEL         = os.getenv("LOG_LEVEL", "INFO")