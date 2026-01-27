#!/usr/bin/env python3
"""LinkedIn Post Curator - Main CLI Application.

This tool:
1. Scrapes top-performing LinkedIn posts about AI/automation
2. Reads your Substack articles from local files
3. Uses Gemini AI to generate LinkedIn posts inspired by top performers
4. Uploads generated posts to Google Sheets for scheduling
"""
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm

from src.config import ARTICLES_DIR, POSTS_TO_FETCH
from src.linkedin_scraper import LinkedInScraper, get_top_ai_posts
from src.article_reader import ArticleReader, load_articles
from src.post_generator import PostGenerator, GeneratedPost
from src.sheets_uploader import SheetsUploader, upload_to_sheets, create_sheet_template

console = Console()


def print_banner():
    """Print the application banner."""
    banner = """
╦  ╦╔╗╔╦╔═╔═╗╔╦╗╦╔╗╔  ╔═╗╔═╗╔═╗╔╦╗  ╔═╗╦ ╦╦═╗╔═╗╔╦╗╔═╗╦═╗
║  ║║║║╠╩╗║╣  ║║║║║║  ╠═╝║ ║╚═╗ ║   ║  ║ ║╠╦╝╠═╣ ║ ║ ║╠╦╝
╩═╝╩╝╚╝╩ ╩╚═╝═╩╝╩╝╚╝  ╩  ╚═╝╚═╝ ╩   ╚═╝╚═╝╩╚═╩ ╩ ╩ ╚═╝╩╚═
    """
    console.print(Panel(banner, style="bold blue", subtitle="AI-Powered LinkedIn Content Creation"))


@click.group()
def cli():
    """LinkedIn Post Curator - Generate engaging LinkedIn posts from your articles."""
    pass


@cli.command()
@click.option('--no-cache', is_flag=True, help='Force fresh scrape, ignore cache')
@click.option('--limit', default=POSTS_TO_FETCH, help='Number of posts to fetch')
def scrape(no_cache, limit):
    """Scrape top-performing AI/automation posts from LinkedIn."""
    print_banner()
    console.print("\n[bold cyan]Scraping LinkedIn for top AI posts...[/bold cyan]\n")

    scraper = LinkedInScraper()
    posts = scraper.get_posts(use_cache=not no_cache)

    if not posts:
        console.print("[yellow]No posts found. Check your LinkedIn credentials.[/yellow]")
        return

    # Display results
    table = Table(title=f"Top {len(posts)} AI/Automation Posts")
    table.add_column("#", style="dim")
    table.add_column("Author")
    table.add_column("Engagement", justify="right")
    table.add_column("Content Preview", max_width=50)

    for i, post in enumerate(posts[:20], 1):
        table.add_row(
            str(i),
            post.author_name[:20],
            str(post.engagement_score),
            post.content[:50] + "..."
        )

    console.print(table)


@cli.command()
def articles():
    """List available articles in the articles directory."""
    print_banner()
    console.print(f"\n[bold cyan]Articles Directory: {ARTICLES_DIR}[/bold cyan]\n")

    reader = ArticleReader()
    available = reader.list_available_articles()

    if not available:
        console.print("[yellow]No articles found.[/yellow]")
        console.print(f"\nAdd your Substack articles as .md or .txt files to:")
        console.print(f"  [cyan]{ARTICLES_DIR}[/cyan]")
        return

    articles = reader.read_directory()
    reader.display_articles()


@cli.command()
@click.argument('article_path', required=False)
@click.option('--num-posts', '-n', default=5, help='Number of posts to generate')
@click.option('--use-inspiration', '-i', is_flag=True, help='Use scraped posts as inspiration')
@click.option('--upload', '-u', is_flag=True, help='Upload to Google Sheets after generation')
def generate(article_path, num_posts, use_inspiration, upload):
    """Generate LinkedIn posts from an article.

    ARTICLE_PATH: Path to the article file (optional - will prompt if not provided)
    """
    print_banner()

    # Load article
    reader = ArticleReader()

    if article_path:
        article = reader.read_file(article_path)
        if not article:
            return
    else:
        # Let user choose from available articles
        available = reader.list_available_articles()

        if not available:
            console.print("[yellow]No articles found in the articles directory.[/yellow]")
            console.print(f"\nAdd markdown or text files to: [cyan]{ARTICLES_DIR}[/cyan]")
            return

        console.print("\n[bold]Available Articles:[/bold]")
        for i, path in enumerate(available, 1):
            console.print(f"  {i}. {path.name}")

        choice = Prompt.ask(
            "\nSelect article number",
            choices=[str(i) for i in range(1, len(available) + 1)]
        )

        article = reader.read_file(available[int(choice) - 1])
        if not article:
            return

    console.print(f"\n[bold cyan]Generating posts from: {article.title}[/bold cyan]\n")

    # Get inspiration posts if requested
    reference_posts = None
    if use_inspiration:
        console.print("[dim]Loading top LinkedIn posts for inspiration...[/dim]")
        scraper = LinkedInScraper()
        reference_posts = scraper.load_cache()
        if not reference_posts:
            console.print("[yellow]No cached posts found. Run 'scrape' command first for inspiration.[/yellow]")

    # Generate posts
    try:
        generator = PostGenerator()
        posts = generator.generate_posts_from_article(
            article=article,
            reference_posts=reference_posts,
            num_posts=num_posts
        )

        if not posts:
            console.print("[red]No posts were generated. Check your Gemini API key.[/red]")
            return

        # Display generated posts
        console.print("\n[bold green]Generated Posts:[/bold green]\n")
        generator.display_posts(posts)

        # Upload to sheets if requested
        if upload:
            if Confirm.ask("Upload these posts to Google Sheets?"):
                uploaded = upload_to_sheets(posts)
                if uploaded:
                    console.print(f"[green]Successfully uploaded {uploaded} posts![/green]")

    except ValueError as e:
        console.print(f"[red]{e}[/red]")


@cli.command()
@click.argument('article_path', required=False)
def curate(article_path):
    """Full workflow: scrape top posts, generate content, upload to sheets.

    This is the main command that runs the complete curation pipeline.
    """
    print_banner()
    console.print("\n[bold cyan]Starting LinkedIn Post Curation Workflow[/bold cyan]\n")

    # Step 1: Load or scrape top posts
    console.print("[bold]Step 1: Loading top-performing posts...[/bold]")
    scraper = LinkedInScraper()
    reference_posts = scraper.load_cache()

    if not reference_posts:
        if Confirm.ask("No cached posts. Scrape LinkedIn now?"):
            reference_posts = scraper.fetch_top_posts()
        else:
            console.print("[yellow]Continuing without inspiration posts...[/yellow]")

    if reference_posts:
        console.print(f"[green]Loaded {len(reference_posts)} reference posts[/green]\n")

    # Step 2: Select article
    console.print("[bold]Step 2: Selecting article...[/bold]")
    reader = ArticleReader()

    if article_path:
        article = reader.read_file(article_path)
    else:
        available = reader.list_available_articles()

        if not available:
            console.print(f"[yellow]No articles found. Add files to: {ARTICLES_DIR}[/yellow]")
            return

        console.print("Available articles:")
        for i, path in enumerate(available, 1):
            console.print(f"  {i}. {path.name}")

        choice = Prompt.ask(
            "Select article",
            choices=[str(i) for i in range(1, len(available) + 1)]
        )
        article = reader.read_file(available[int(choice) - 1])

    if not article:
        return

    console.print(f"[green]Selected: {article.title}[/green]\n")

    # Step 3: Generate posts
    console.print("[bold]Step 3: Generating LinkedIn posts...[/bold]")
    num_posts = int(Prompt.ask("How many posts to generate?", default="5"))

    try:
        generator = PostGenerator()
        posts = generator.generate_posts_from_article(
            article=article,
            reference_posts=reference_posts,
            num_posts=num_posts
        )

        if not posts:
            console.print("[red]Failed to generate posts.[/red]")
            return

        generator.display_posts(posts)

    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        return

    # Step 4: Upload to Google Sheets
    console.print("\n[bold]Step 4: Upload to Google Sheets[/bold]")

    if Confirm.ask("Upload generated posts to Google Sheets?"):
        uploader = SheetsUploader()
        if uploader.connect():
            uploaded = uploader.upload_posts(posts)
            console.print(f"\n[bold green]Workflow complete! Uploaded {uploaded} posts.[/bold green]")
        else:
            console.print("[yellow]Could not connect to Google Sheets.[/yellow]")
            console.print("Posts are displayed above - you can copy them manually.")
    else:
        console.print("\n[bold green]Workflow complete![/bold green]")
        console.print("Posts are displayed above.")


@cli.command()
def sheets():
    """Test Google Sheets connection and view uploaded posts."""
    print_banner()
    console.print("\n[bold cyan]Google Sheets Integration[/bold cyan]\n")

    uploader = SheetsUploader()

    if uploader.connect():
        uploader.display_sheet_summary()
    else:
        console.print("\n[yellow]Setup Instructions:[/yellow]")
        console.print(create_sheet_template())


@cli.command()
def setup():
    """Display setup instructions for all integrations."""
    print_banner()

    console.print("\n[bold cyan]Setup Instructions[/bold cyan]\n")

    # Environment setup
    console.print(Panel("""
[bold]1. Create Environment File[/bold]

Copy .env.example to .env and fill in your credentials:

    cp .env.example .env

[bold]2. LinkedIn Credentials[/bold]

Add your LinkedIn email and password to .env:

    LINKEDIN_EMAIL=your_email@example.com
    LINKEDIN_PASSWORD=your_password

[bold]3. Gemini API Key[/bold]

Get your API key from: https://makersuite.google.com/app/apikey
Add to .env:

    GEMINI_API_KEY=your_api_key

[bold]4. Google Sheets (see 'linkedin-curator sheets' for detailed instructions)[/bold]

    - Create a Google Cloud project
    - Enable Sheets API
    - Create service account
    - Download credentials JSON
    - Share your sheet with the service account

[bold]5. Add Your Articles[/bold]

Place your Substack articles in the articles/ directory:

    articles/
    ├── my-first-article.md
    ├── ai-automation-tips.txt
    └── future-of-work.md
""", title="Setup Guide"))


@cli.command()
def version():
    """Show version information."""
    console.print("LinkedIn Post Curator v1.0.0")


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
