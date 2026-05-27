import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN: str = os.environ.get("DISCORD_TOKEN", "")

if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_TOKEN is not set. Copy .env.example to .env and fill in your token.")
