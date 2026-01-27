"""FastAPI backend for LinkedIn Post Curator."""
import os
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.config import ARTICLES_DIR, CACHE_DIR, GEMINI_API_KEY
from src.linkedin_scraper import LinkedInScraper, LinkedInPost
from src.article_reader import ArticleReader, Article
from src.post_generator import PostGenerator, GeneratedPost
from src.sheets_uploader import SheetsUploader

app = FastAPI(title="LinkedIn Post Curator", version="1.0.0")

# CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state for background tasks
scraping_status = {"running": False, "progress": "", "posts": []}
generation_status = {"running": False, "progress": "", "posts": []}


# ============ Pydantic Models ============

class ArticleCreate(BaseModel):
    title: str
    content: str
    filename: Optional[str] = None


class ArticleUpdate(BaseModel):
    content: str


class GenerateRequest(BaseModel):
    article_path: str
    num_posts: int = 5
    use_inspiration: bool = False
    post_styles: Optional[list[str]] = None


class ContentIdea(BaseModel):
    hook: str
    theme: str
    format_suggestion: str
    engagement_potential: str


# ============ Article Endpoints ============

@app.get("/api/articles")
async def list_articles():
    """List all articles in the articles directory."""
    reader = ArticleReader()
    articles = reader.read_directory()
    return {
        "articles": [
            {
                "title": a.title,
                "content": a.content,
                "file_path": a.file_path,
                "filename": Path(a.file_path).name,
                "word_count": a.word_count,
                "loaded_at": a.loaded_at.isoformat()
            }
            for a in articles
        ]
    }


@app.get("/api/articles/{filename}")
async def get_article(filename: str):
    """Get a specific article by filename."""
    file_path = ARTICLES_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Article not found")

    reader = ArticleReader()
    article = reader.read_file(file_path)
    if not article:
        raise HTTPException(status_code=500, detail="Failed to read article")

    return {
        "title": article.title,
        "content": article.content,
        "file_path": article.file_path,
        "filename": filename,
        "word_count": article.word_count
    }


@app.post("/api/articles")
async def create_article(article: ArticleCreate):
    """Create a new article."""
    # Generate filename if not provided
    if not article.filename:
        safe_title = "".join(c if c.isalnum() or c in " -_" else "" for c in article.title)
        safe_title = safe_title.replace(" ", "-").lower()[:50]
        article.filename = f"{safe_title}.md"

    # Ensure .md extension
    if not article.filename.endswith(('.md', '.txt')):
        article.filename += '.md'

    file_path = ARTICLES_DIR / article.filename

    # Don't overwrite existing files
    if file_path.exists():
        raise HTTPException(status_code=400, detail="Article with this filename already exists")

    # Write the file
    content = f"# {article.title}\n\n{article.content}"
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    return {"message": "Article created", "filename": article.filename}


@app.put("/api/articles/{filename}")
async def update_article(filename: str, article: ArticleUpdate):
    """Update an existing article."""
    file_path = ARTICLES_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Article not found")

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(article.content)

    return {"message": "Article updated", "filename": filename}


@app.delete("/api/articles/{filename}")
async def delete_article(filename: str):
    """Delete an article."""
    file_path = ARTICLES_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Article not found")

    os.remove(file_path)
    return {"message": "Article deleted", "filename": filename}


# ============ LinkedIn Scraping Endpoints ============

@app.get("/api/linkedin/posts")
async def get_cached_posts():
    """Get cached LinkedIn posts."""
    scraper = LinkedInScraper()
    posts = scraper.load_cache(max_age_hours=168)  # 1 week cache

    return {
        "posts": [p.to_dict() for p in posts],
        "count": len(posts),
        "cached": True
    }


@app.post("/api/linkedin/scrape")
async def start_scrape(background_tasks: BackgroundTasks):
    """Start LinkedIn scraping in background."""
    if scraping_status["running"]:
        raise HTTPException(status_code=400, detail="Scraping already in progress")

    def run_scrape():
        scraping_status["running"] = True
        scraping_status["progress"] = "Starting scraper..."
        scraping_status["posts"] = []

        try:
            scraper = LinkedInScraper()
            scraping_status["progress"] = "Logging in to LinkedIn..."
            posts = scraper.fetch_top_posts()
            scraping_status["posts"] = [p.to_dict() for p in posts]
            scraping_status["progress"] = f"Completed! Found {len(posts)} posts."
        except Exception as e:
            scraping_status["progress"] = f"Error: {str(e)}"
        finally:
            scraping_status["running"] = False

    background_tasks.add_task(run_scrape)
    return {"message": "Scraping started", "status": "running"}


@app.get("/api/linkedin/scrape/status")
async def get_scrape_status():
    """Get current scraping status."""
    return scraping_status


# ============ Content Ideas Endpoints ============

@app.get("/api/ideas")
async def get_content_ideas():
    """Generate content ideas based on top LinkedIn posts."""
    scraper = LinkedInScraper()
    posts = scraper.load_cache(max_age_hours=168)

    if not posts:
        return {
            "ideas": [],
            "message": "No cached posts. Run LinkedIn scan first."
        }

    # Extract patterns and generate ideas
    ideas = []

    # Analyze top posts for patterns
    hooks = []
    themes = set()

    for post in posts[:10]:
        # Extract first line as hook pattern
        first_line = post.content.split('\n')[0][:100]
        hooks.append(first_line)

        # Extract themes
        content_lower = post.content.lower()
        if 'ai' in content_lower or 'artificial intelligence' in content_lower:
            themes.add('AI/Machine Learning')
        if 'automat' in content_lower:
            themes.add('Automation')
        if 'productiv' in content_lower:
            themes.add('Productivity')
        if 'future' in content_lower:
            themes.add('Future Trends')
        if 'tool' in content_lower or 'app' in content_lower:
            themes.add('Tools & Apps')

    # Generate ideas based on patterns
    for i, post in enumerate(posts[:5]):
        hook = post.content.split('\n')[0][:80]

        # Determine format
        if any(char.isdigit() for char in post.content[:50]):
            format_type = "Listicle"
        elif '?' in post.content[:100]:
            format_type = "Question-led"
        else:
            format_type = "Story/Insight"

        # Engagement potential based on score
        if post.engagement_score > 500:
            potential = "High"
        elif post.engagement_score > 100:
            potential = "Medium"
        else:
            potential = "Low-Medium"

        ideas.append({
            "id": i + 1,
            "hook_pattern": hook + "...",
            "theme": list(themes)[i % len(themes)] if themes else "AI & Technology",
            "format_suggestion": format_type,
            "engagement_potential": potential,
            "original_engagement": post.engagement_score,
            "author": post.author_name,
            "source_preview": post.content[:200] + "..."
        })

    return {
        "ideas": ideas,
        "trending_themes": list(themes),
        "total_posts_analyzed": len(posts)
    }


# ============ Post Generation Endpoints ============

@app.post("/api/generate")
async def generate_posts(request: GenerateRequest, background_tasks: BackgroundTasks):
    """Generate LinkedIn posts from an article."""
    if generation_status["running"]:
        raise HTTPException(status_code=400, detail="Generation already in progress")

    # Verify article exists
    file_path = Path(request.article_path)
    if not file_path.exists():
        # Try with articles directory
        file_path = ARTICLES_DIR / request.article_path

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Article not found")

    def run_generation():
        generation_status["running"] = True
        generation_status["progress"] = "Loading article..."
        generation_status["posts"] = []

        try:
            # Load article
            reader = ArticleReader()
            article = reader.read_file(file_path)

            if not article:
                generation_status["progress"] = "Failed to load article"
                return

            # Load reference posts if requested
            reference_posts = None
            if request.use_inspiration:
                generation_status["progress"] = "Loading inspiration posts..."
                scraper = LinkedInScraper()
                reference_posts = scraper.load_cache()

            generation_status["progress"] = "Generating posts with Gemini AI..."

            # Generate posts
            generator = PostGenerator()
            posts = generator.generate_posts_from_article(
                article=article,
                reference_posts=reference_posts,
                num_posts=request.num_posts,
                post_styles=request.post_styles
            )

            generation_status["posts"] = [p.to_dict() for p in posts]
            generation_status["progress"] = f"Generated {len(posts)} posts!"

        except Exception as e:
            generation_status["progress"] = f"Error: {str(e)}"
        finally:
            generation_status["running"] = False

    background_tasks.add_task(run_generation)
    return {"message": "Generation started", "status": "running"}


@app.get("/api/generate/status")
async def get_generation_status():
    """Get current generation status."""
    return generation_status


# ============ Google Sheets Endpoints ============

@app.post("/api/sheets/upload")
async def upload_to_sheets(posts: list[dict]):
    """Upload generated posts to Google Sheets."""
    try:
        uploader = SheetsUploader()
        if not uploader.connect():
            raise HTTPException(status_code=500, detail="Failed to connect to Google Sheets")

        # Convert dicts to GeneratedPost objects
        generated_posts = []
        for p in posts:
            post = GeneratedPost(
                content=p["content"],
                hook=p["hook"],
                source_article_title=p["source_article_title"],
                post_type=p["post_type"],
                estimated_engagement=p["estimated_engagement"],
                hashtags=p.get("hashtags", []),
                call_to_action=p.get("call_to_action", ""),
                generated_at=datetime.fromisoformat(p["generated_at"]) if isinstance(p.get("generated_at"), str) else datetime.now()
            )
            generated_posts.append(post)

        count = uploader.upload_posts(generated_posts)
        return {"message": f"Uploaded {count} posts to Google Sheets", "count": count}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ Health & Config Endpoints ============

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "gemini_configured": bool(GEMINI_API_KEY),
        "articles_dir": str(ARTICLES_DIR),
        "cache_dir": str(CACHE_DIR)
    }


@app.get("/api/config")
async def get_config():
    """Get current configuration status."""
    from src.config import LINKEDIN_EMAIL, GOOGLE_SHEET_ID

    return {
        "linkedin_configured": bool(LINKEDIN_EMAIL),
        "gemini_configured": bool(GEMINI_API_KEY),
        "sheets_configured": bool(GOOGLE_SHEET_ID),
        "articles_count": len(list(ARTICLES_DIR.glob("*.md")) + list(ARTICLES_DIR.glob("*.txt")))
    }


# ============ Static Files & Frontend ============

# Serve the frontend
@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the main frontend page."""
    static_dir = Path(__file__).parent.parent / "static"
    index_path = static_dir / "index.html"

    if index_path.exists():
        with open(index_path, 'r') as f:
            return HTMLResponse(content=f.read())

    return HTMLResponse(content="<h1>Frontend not found</h1>", status_code=404)
