import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ASSEMBLYAI_API_KEY")
if not API_KEY:
    raise ValueError("ASSEMBLYAI_API_KEY not found in environment variables or .env file")

MEETINGS_DIR = Path.home() / "work" / "meetingreco" / "meetings"
MEETINGS_DIR.mkdir(exist_ok=True, parents=True)

BITRATE = "192k"
SPEAKERS_EXPECTED = None

TEMP_DIR = Path("/tmp")
APP_NAME = "Meeting Recorder"