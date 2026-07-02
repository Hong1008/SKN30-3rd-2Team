
import os
from dotenv import load_dotenv
from pathlib import Path

app_env = os.getenv("APP_ENV", "local")
load_dotenv()

WORKSHIELD_MCP_URL = os.getenv('WORKSHIELD_MCP_URL', 'http://localhost:8000/mcp')
