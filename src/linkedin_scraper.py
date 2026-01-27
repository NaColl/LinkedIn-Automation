"""LinkedIn post scraper for fetching top AI/automation content."""
import time
import random
import pickle
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.config import (
    LINKEDIN_EMAIL,
    LINKEDIN_PASSWORD,
    HEADLESS_BROWSER,
    POSTS_TO_FETCH,
    AI_SEARCH_KEYWORDS,
    CACHE_DIR
)

console = Console()


@dataclass
class LinkedInPost:
    """Represents a LinkedIn post."""
    author_name: str
    author_headline: str
    author_profile_url: str
    content: str
    post_url: str
    likes_count: int = 0
    comments_count: int = 0
    reposts_count: int = 0
    engagement_score: int = 0
    scraped_at: datetime = field(default_factory=datetime.now)

    def calculate_engagement(self):
        """Calculate engagement score based on reactions."""
        self.engagement_score = self.likes_count + (self.comments_count * 2) + (self.reposts_count * 3)
        return self.engagement_score

    def to_dict(self):
        """Convert to dictionary for storage."""
        return {
            "author_name": self.author_name,
            "author_headline": self.author_headline,
            "author_profile_url": self.author_profile_url,
            "content": self.content,
            "post_url": self.post_url,
            "likes_count": self.likes_count,
            "comments_count": self.comments_count,
            "reposts_count": self.reposts_count,
            "engagement_score": self.engagement_score,
            "scraped_at": self.scraped_at.isoformat()
        }


class LinkedInScraper:
    """Scrapes LinkedIn for top-performing AI/automation posts."""

    def __init__(self):
        self.driver: Optional[webdriver.Chrome] = None
        self.posts: list[LinkedInPost] = []
        self.cache_file = CACHE_DIR / "linkedin_posts_cache.pkl"

    def _setup_driver(self):
        """Initialize Chrome WebDriver with appropriate options."""
        options = Options()

        if HEADLESS_BROWSER:
            options.add_argument("--headless=new")

        # Anti-detection measures
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

        # Disable automation flags
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)

        # Execute CDP commands to mask automation
        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            """
        })

    def _random_delay(self, min_sec=1, max_sec=3):
        """Add random delay to mimic human behavior."""
        time.sleep(random.uniform(min_sec, max_sec))

    def login(self) -> bool:
        """Log in to LinkedIn."""
        if not LINKEDIN_EMAIL or not LINKEDIN_PASSWORD:
            console.print("[red]LinkedIn credentials not set in .env file[/red]")
            return False

        try:
            console.print("[yellow]Logging in to LinkedIn...[/yellow]")
            self.driver.get("https://www.linkedin.com/login")
            self._random_delay(2, 4)

            # Enter email
            email_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            email_field.send_keys(LINKEDIN_EMAIL)
            self._random_delay(0.5, 1)

            # Enter password
            password_field = self.driver.find_element(By.ID, "password")
            password_field.send_keys(LINKEDIN_PASSWORD)
            self._random_delay(0.5, 1)

            # Click login button
            login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            login_button.click()

            # Wait for login to complete
            self._random_delay(3, 5)

            # Check if login successful
            if "feed" in self.driver.current_url or "checkpoint" not in self.driver.current_url:
                console.print("[green]Successfully logged in to LinkedIn[/green]")
                return True
            else:
                console.print("[red]Login may have failed or requires verification[/red]")
                return False

        except TimeoutException:
            console.print("[red]Timeout during login[/red]")
            return False
        except Exception as e:
            console.print(f"[red]Login error: {e}[/red]")
            return False

    def _parse_engagement_count(self, text: str) -> int:
        """Parse engagement count from text like '1.2K' or '500'."""
        if not text:
            return 0
        text = text.strip().lower()
        try:
            if 'k' in text:
                return int(float(text.replace('k', '')) * 1000)
            elif 'm' in text:
                return int(float(text.replace('m', '')) * 1000000)
            else:
                return int(text.replace(',', ''))
        except (ValueError, AttributeError):
            return 0

    def _extract_post_data(self, post_element) -> Optional[LinkedInPost]:
        """Extract data from a single post element."""
        try:
            soup = BeautifulSoup(post_element.get_attribute('innerHTML'), 'html.parser')

            # Extract author info
            author_link = soup.select_one('a.app-aware-link[href*="/in/"]')
            author_name = ""
            author_profile_url = ""

            if author_link:
                author_name = author_link.get_text(strip=True)
                author_profile_url = author_link.get('href', '')
                if author_profile_url and not author_profile_url.startswith('http'):
                    author_profile_url = f"https://www.linkedin.com{author_profile_url}"

            # Extract headline
            headline_elem = soup.select_one('.update-components-actor__description')
            author_headline = headline_elem.get_text(strip=True) if headline_elem else ""

            # Extract post content
            content_elem = soup.select_one('.feed-shared-update-v2__description, .update-components-text')
            content = content_elem.get_text(strip=True) if content_elem else ""

            if not content or len(content) < 50:
                return None

            # Extract post URL
            post_url = ""
            activity_link = soup.select_one('a[href*="/activity/"]')
            if activity_link:
                post_url = activity_link.get('href', '')
                if post_url and not post_url.startswith('http'):
                    post_url = f"https://www.linkedin.com{post_url}"

            # Extract engagement metrics
            likes_text = ""
            comments_text = ""
            reposts_text = ""

            social_counts = soup.select('.social-details-social-counts span')
            for count in social_counts:
                text = count.get_text(strip=True).lower()
                if 'reaction' in text or 'like' in text:
                    likes_text = text.split()[0]
                elif 'comment' in text:
                    comments_text = text.split()[0]
                elif 'repost' in text:
                    reposts_text = text.split()[0]

            post = LinkedInPost(
                author_name=author_name,
                author_headline=author_headline,
                author_profile_url=author_profile_url,
                content=content[:2000],  # Limit content length
                post_url=post_url,
                likes_count=self._parse_engagement_count(likes_text),
                comments_count=self._parse_engagement_count(comments_text),
                reposts_count=self._parse_engagement_count(reposts_text)
            )
            post.calculate_engagement()

            return post

        except Exception as e:
            console.print(f"[dim]Error extracting post: {e}[/dim]")
            return None

    def search_posts(self, keyword: str, max_posts: int = 10) -> list[LinkedInPost]:
        """Search for posts with a specific keyword."""
        posts = []

        try:
            # Navigate to search
            search_url = f"https://www.linkedin.com/search/results/content/?keywords={keyword}&sortBy=%22relevance%22&datePosted=%22past-week%22"
            self.driver.get(search_url)
            self._random_delay(3, 5)

            # Scroll to load more posts
            scroll_count = 0
            max_scrolls = 5

            while len(posts) < max_posts and scroll_count < max_scrolls:
                # Find post containers
                post_elements = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    ".feed-shared-update-v2, .update-components-update-v2"
                )

                for post_elem in post_elements:
                    if len(posts) >= max_posts:
                        break

                    post = self._extract_post_data(post_elem)
                    if post and post.content not in [p.content for p in posts]:
                        posts.append(post)

                # Scroll down
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                self._random_delay(2, 4)
                scroll_count += 1

        except Exception as e:
            console.print(f"[red]Error searching for '{keyword}': {e}[/red]")

        return posts

    def fetch_top_posts(self, keywords: list[str] = None) -> list[LinkedInPost]:
        """Fetch top-performing posts for given keywords."""
        if keywords is None:
            keywords = AI_SEARCH_KEYWORDS

        all_posts = []

        try:
            self._setup_driver()

            if not self.login():
                console.print("[red]Failed to login. Cannot fetch posts.[/red]")
                return []

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:

                for keyword in keywords:
                    task = progress.add_task(f"Searching for '{keyword}'...", total=None)
                    posts = self.search_posts(keyword, max_posts=POSTS_TO_FETCH // len(keywords))
                    all_posts.extend(posts)
                    progress.remove_task(task)
                    self._random_delay(2, 4)

            # Remove duplicates and sort by engagement
            seen_contents = set()
            unique_posts = []
            for post in all_posts:
                content_hash = hash(post.content[:100])
                if content_hash not in seen_contents:
                    seen_contents.add(content_hash)
                    unique_posts.append(post)

            # Sort by engagement score
            unique_posts.sort(key=lambda p: p.engagement_score, reverse=True)

            self.posts = unique_posts[:POSTS_TO_FETCH]

            # Cache the results
            self._save_cache()

            console.print(f"[green]Fetched {len(self.posts)} top-performing posts[/green]")

        finally:
            if self.driver:
                self.driver.quit()

        return self.posts

    def _save_cache(self):
        """Save posts to cache file."""
        cache_data = {
            "posts": [p.to_dict() for p in self.posts],
            "cached_at": datetime.now().isoformat()
        }
        with open(self.cache_file, 'wb') as f:
            pickle.dump(cache_data, f)

    def load_cache(self, max_age_hours: int = 24) -> list[LinkedInPost]:
        """Load posts from cache if not too old."""
        if not self.cache_file.exists():
            return []

        try:
            with open(self.cache_file, 'rb') as f:
                cache_data = pickle.load(f)

            cached_at = datetime.fromisoformat(cache_data["cached_at"])
            if datetime.now() - cached_at > timedelta(hours=max_age_hours):
                return []

            self.posts = []
            for p_dict in cache_data["posts"]:
                post = LinkedInPost(
                    author_name=p_dict["author_name"],
                    author_headline=p_dict["author_headline"],
                    author_profile_url=p_dict["author_profile_url"],
                    content=p_dict["content"],
                    post_url=p_dict["post_url"],
                    likes_count=p_dict["likes_count"],
                    comments_count=p_dict["comments_count"],
                    reposts_count=p_dict["reposts_count"],
                    engagement_score=p_dict["engagement_score"],
                    scraped_at=datetime.fromisoformat(p_dict["scraped_at"])
                )
                self.posts.append(post)

            console.print(f"[cyan]Loaded {len(self.posts)} posts from cache[/cyan]")
            return self.posts

        except Exception as e:
            console.print(f"[yellow]Could not load cache: {e}[/yellow]")
            return []

    def get_posts(self, use_cache: bool = True, cache_max_age: int = 24) -> list[LinkedInPost]:
        """Get posts, using cache if available and fresh."""
        if use_cache:
            cached = self.load_cache(cache_max_age)
            if cached:
                return cached

        return self.fetch_top_posts()


def get_top_ai_posts(use_cache: bool = True) -> list[LinkedInPost]:
    """Convenience function to get top AI posts."""
    scraper = LinkedInScraper()
    return scraper.get_posts(use_cache=use_cache)


if __name__ == "__main__":
    # Test the scraper
    posts = get_top_ai_posts(use_cache=False)
    for i, post in enumerate(posts[:5], 1):
        console.print(f"\n[bold]Post {i}[/bold]")
        console.print(f"Author: {post.author_name}")
        console.print(f"Engagement: {post.engagement_score}")
        console.print(f"Content: {post.content[:200]}...")
