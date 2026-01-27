"""Article reader for loading Substack/blog content from local files."""
import os
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import markdown
from rich.console import Console
from rich.table import Table

from src.config import ARTICLES_DIR

console = Console()


@dataclass
class Article:
    """Represents a Substack or blog article."""
    title: str
    content: str
    file_path: str
    summary: Optional[str] = None
    key_points: list[str] = field(default_factory=list)
    word_count: int = 0
    loaded_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        self.word_count = len(self.content.split())

    def to_dict(self):
        """Convert to dictionary."""
        return {
            "title": self.title,
            "content": self.content,
            "file_path": self.file_path,
            "summary": self.summary,
            "key_points": self.key_points,
            "word_count": self.word_count,
            "loaded_at": self.loaded_at.isoformat()
        }


class ArticleReader:
    """Reads and processes articles from local markdown/text files."""

    SUPPORTED_EXTENSIONS = {'.md', '.markdown', '.txt', '.text'}

    def __init__(self, articles_dir: Path = None):
        self.articles_dir = articles_dir or ARTICLES_DIR
        self.articles: list[Article] = []

    def _extract_title_from_content(self, content: str, filename: str) -> str:
        """Extract title from content or use filename."""
        lines = content.strip().split('\n')

        # Check for markdown header
        for line in lines[:5]:  # Check first 5 lines
            line = line.strip()
            if line.startswith('# '):
                return line[2:].strip()
            if line.startswith('## '):
                return line[3:].strip()

        # Use filename without extension
        return Path(filename).stem.replace('-', ' ').replace('_', ' ').title()

    def _clean_content(self, content: str) -> str:
        """Clean and normalize content."""
        # Remove multiple consecutive newlines
        import re
        content = re.sub(r'\n{3,}', '\n\n', content)

        # Strip leading/trailing whitespace
        content = content.strip()

        return content

    def read_file(self, file_path: str | Path) -> Optional[Article]:
        """Read a single article from a file."""
        file_path = Path(file_path)

        if not file_path.exists():
            console.print(f"[red]File not found: {file_path}[/red]")
            return None

        if file_path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            console.print(f"[yellow]Unsupported file type: {file_path.suffix}[/yellow]")
            return None

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            content = self._clean_content(content)
            title = self._extract_title_from_content(content, file_path.name)

            article = Article(
                title=title,
                content=content,
                file_path=str(file_path)
            )

            console.print(f"[green]Loaded article: {title} ({article.word_count} words)[/green]")
            return article

        except Exception as e:
            console.print(f"[red]Error reading {file_path}: {e}[/red]")
            return None

    def read_directory(self, directory: Path = None) -> list[Article]:
        """Read all articles from a directory."""
        directory = directory or self.articles_dir
        directory = Path(directory)

        if not directory.exists():
            console.print(f"[yellow]Creating articles directory: {directory}[/yellow]")
            directory.mkdir(parents=True, exist_ok=True)
            return []

        articles = []

        for file_path in directory.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                article = self.read_file(file_path)
                if article:
                    articles.append(article)

        self.articles = articles
        return articles

    def list_available_articles(self) -> list[Path]:
        """List all available article files in the directory."""
        if not self.articles_dir.exists():
            return []

        return [
            f for f in self.articles_dir.iterdir()
            if f.is_file() and f.suffix.lower() in self.SUPPORTED_EXTENSIONS
        ]

    def display_articles(self):
        """Display loaded articles in a table."""
        if not self.articles:
            console.print("[yellow]No articles loaded[/yellow]")
            return

        table = Table(title="Loaded Articles")
        table.add_column("Title", style="cyan")
        table.add_column("Words", justify="right")
        table.add_column("File", style="dim")

        for article in self.articles:
            table.add_row(
                article.title[:50] + "..." if len(article.title) > 50 else article.title,
                str(article.word_count),
                Path(article.file_path).name
            )

        console.print(table)


def load_articles(directory: Path = None) -> list[Article]:
    """Convenience function to load all articles from a directory."""
    reader = ArticleReader(directory)
    return reader.read_directory()


def load_article(file_path: str | Path) -> Optional[Article]:
    """Convenience function to load a single article."""
    reader = ArticleReader()
    return reader.read_file(file_path)


if __name__ == "__main__":
    # Test the reader
    console.print("[bold]Article Reader Test[/bold]")
    console.print(f"Articles directory: {ARTICLES_DIR}")

    # List available articles
    reader = ArticleReader()
    available = reader.list_available_articles()

    if available:
        console.print(f"\nFound {len(available)} article(s):")
        for f in available:
            console.print(f"  - {f.name}")

        articles = reader.read_directory()
        reader.display_articles()
    else:
        console.print("\n[yellow]No articles found. Add markdown or text files to the 'articles' directory.[/yellow]")
        console.print(f"Directory: {ARTICLES_DIR}")
