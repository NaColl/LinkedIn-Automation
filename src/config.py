"""Configuration management for LinkedIn Automation Tool."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base paths
BASE_DIR = Path(__file__).parent.parent
ARTICLES_DIR = BASE_DIR / "articles"
CACHE_DIR = BASE_DIR / "cache"

# Ensure directories exist
ARTICLES_DIR.mkdir(exist_ok=True)
CACHE_DIR.mkdir(exist_ok=True)

# LinkedIn settings
LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL", "")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD", "")

# Gemini settings
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Google Sheets settings
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials/google_service_account.json")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")
GOOGLE_WORKSHEET_NAME = os.getenv("GOOGLE_WORKSHEET_NAME", "LinkedIn Posts")

# Scraping settings
POSTS_TO_FETCH = int(os.getenv("POSTS_TO_FETCH", "20"))
HEADLESS_BROWSER = os.getenv("HEADLESS_BROWSER", "true").lower() == "true"

# AI topics to search for
AI_SEARCH_KEYWORDS = [
    "AI automation",
    "artificial intelligence",
    "machine learning",
    "generative AI",
    "AI agents",
    "LLM",
    "ChatGPT",
    "Claude AI",
    "AI tools",
    "AI productivity"
]

# Top AI influencers on LinkedIn to monitor
AI_INFLUENCERS = [
    "satloani",        # Harpreet Marwah
    "alaboratory",     # Allie K. Miller
    "samszucki",       # Sam Szucki
    "artificialintellectai",
    "ai-automation-hub",
]
