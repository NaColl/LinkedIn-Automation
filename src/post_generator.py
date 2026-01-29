"""LinkedIn post generator using Google Gemini."""
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import google.generativeai as genai
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.config import GEMINI_API_KEY
from src.linkedin_scraper import LinkedInPost
from src.article_reader import Article

console = Console()


@dataclass
class GeneratedPost:
    """Represents a generated LinkedIn post."""
    content: str
    hook: str
    source_article_title: str
    post_type: str  # e.g., "listicle", "story", "insight", "question"
    estimated_engagement: str  # "low", "medium", "high"
    hashtags: list[str] = field(default_factory=list)
    call_to_action: str = ""
    generated_at: datetime = field(default_factory=datetime.now)
    inspiration_posts: list[str] = field(default_factory=list)

    def to_dict(self):
        """Convert to dictionary for storage."""
        return {
            "content": self.content,
            "hook": self.hook,
            "source_article_title": self.source_article_title,
            "post_type": self.post_type,
            "estimated_engagement": self.estimated_engagement,
            "hashtags": self.hashtags,
            "call_to_action": self.call_to_action,
            "generated_at": self.generated_at.isoformat(),
            "inspiration_posts": self.inspiration_posts
        }

    def format_for_linkedin(self) -> str:
        """Format the post ready for LinkedIn."""
        hashtag_str = " ".join(f"#{tag}" for tag in self.hashtags) if self.hashtags else ""
        return f"{self.content}\n\n{hashtag_str}".strip()


class PostGenerator:
    """Generates LinkedIn posts using Gemini AI."""

    def __init__(self):
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not set in environment variables")

        genai.configure(api_key=GEMINI_API_KEY)

        # Configure generation settings
        generation_config = {
            "temperature": 0.9,
            "top_p": 0.95,
            "max_output_tokens": 2048,
        }

        # Reduce safety filtering for content generation
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
        ]

        # Find available models that support generateContent
        self.model = None
        available_models = []

        try:
            for m in genai.list_models():
                if 'generateContent' in [method.name for method in m.supported_generation_methods]:
                    available_models.append(m.name)
        except Exception as e:
            console.print(f"[yellow]Could not list models: {e}[/yellow]")

        if available_models:
            console.print(f"[dim]Available models: {available_models[:5]}[/dim]")

        # Preferred models in order
        preferred = ['models/gemini-2.0-flash', 'models/gemini-1.5-flash', 'models/gemini-1.5-pro', 'models/gemini-pro']

        # Try preferred models first, then any available
        models_to_try = []
        for p in preferred:
            if p in available_models:
                models_to_try.append(p)
        # Add any other available models
        for m in available_models:
            if m not in models_to_try and 'gemini' in m.lower():
                models_to_try.append(m)

        # Fallback to hardcoded if list_models failed
        if not models_to_try:
            models_to_try = ['gemini-2.0-flash-exp', 'gemini-1.5-flash-latest', 'gemini-1.5-pro-latest', 'gemini-pro']

        for model_name in models_to_try:
            try:
                # Remove 'models/' prefix if present for GenerativeModel
                clean_name = model_name.replace('models/', '')
                self.model = genai.GenerativeModel(
                    clean_name,
                    generation_config=generation_config,
                    safety_settings=safety_settings
                )
                # Test if model works
                test_response = self.model.generate_content("Say ok")
                if test_response.text:
                    console.print(f"[green]Using model: {clean_name}[/green]")
                    break
            except Exception as e:
                console.print(f"[yellow]Model {model_name} failed: {str(e)[:60]}...[/yellow]")
                self.model = None
                continue

        if self.model is None:
            raise ValueError(f"No compatible Gemini model found. Available: {available_models}. Check your API key.")
        self.generated_posts: list[GeneratedPost] = []
        self.errors: list[str] = []  # Track errors for debugging

    def _analyze_top_posts(self, posts: list[LinkedInPost]) -> str:
        """Analyze top posts to understand what makes them successful."""
        if not posts:
            return "No reference posts available."

        analysis_prompt = f"""Analyze these top-performing LinkedIn posts about AI and automation.
Identify patterns in:
1. Hook styles (first line)
2. Content structure
3. Engagement triggers
4. Formatting techniques
5. Call-to-action styles

Posts to analyze:
{self._format_posts_for_analysis(posts[:10])}

Provide a concise summary of the successful patterns."""

        try:
            response = self.model.generate_content(analysis_prompt)
            return response.text
        except Exception as e:
            console.print(f"[yellow]Could not analyze posts: {e}[/yellow]")
            return "Use proven LinkedIn patterns: strong hook, storytelling, value-driven content, clear CTA."

    def _format_posts_for_analysis(self, posts: list[LinkedInPost]) -> str:
        """Format posts for analysis prompt."""
        formatted = []
        for i, post in enumerate(posts, 1):
            formatted.append(f"""
--- Post {i} (Engagement: {post.engagement_score}) ---
{post.content[:500]}...
""")
        return "\n".join(formatted)

    def generate_posts_from_article(
        self,
        article: Article,
        reference_posts: list[LinkedInPost] = None,
        num_posts: int = 5,
        post_styles: list[str] = None
    ) -> list[GeneratedPost]:
        """Generate multiple LinkedIn posts from a single article."""

        if post_styles is None:
            post_styles = ["hook-story", "listicle", "question", "insight", "contrarian"]

        # Analyze top posts for inspiration
        patterns_analysis = ""
        if reference_posts:
            with console.status("[bold green]Analyzing top-performing posts..."):
                patterns_analysis = self._analyze_top_posts(reference_posts)

        generated = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Generating posts...", total=num_posts)

            for i, style in enumerate(post_styles[:num_posts]):
                progress.update(task, description=f"Generating {style} post...")

                post = self._generate_single_post(
                    article=article,
                    style=style,
                    patterns_analysis=patterns_analysis,
                    reference_posts=reference_posts
                )

                if post:
                    generated.append(post)

                progress.advance(task)

        self.generated_posts.extend(generated)
        console.print(f"[green]Generated {len(generated)} posts from '{article.title}'[/green]")

        return generated

    def _generate_single_post(
        self,
        article: Article,
        style: str,
        patterns_analysis: str = "",
        reference_posts: list[LinkedInPost] = None
    ) -> Optional[GeneratedPost]:
        """Generate a single LinkedIn post in a specific style."""

        style_instructions = {
            "hook-story": """
Create a post with a powerful hook (first line) that stops scrolling.
Follow with a personal story or anecdote related to the article's main point.
End with a thought-provoking insight or question.""",

            "listicle": """
Create a numbered list post (5-7 items).
Start with a bold claim or statistic.
Each item should be actionable and valuable.
Use line breaks for readability.""",

            "question": """
Start with a thought-provoking question.
Share contrasting perspectives from the article.
Invite discussion and different viewpoints.
End with another question to drive comments.""",

            "insight": """
Share a counterintuitive insight or "aha moment" from the article.
Explain why it matters.
Provide practical application.
Keep it punchy and direct.""",

            "contrarian": """
Challenge a common belief related to the article's topic.
Present the alternative viewpoint with evidence.
Be bold but respectful.
Invite debate in the comments."""
        }

        prompt = f"""You are an expert LinkedIn content creator specializing in AI and technology content.

TASK: Create a LinkedIn post based on this article, using the "{style}" style.

ARTICLE TITLE: {article.title}

ARTICLE CONTENT:
{article.content[:4000]}

STYLE INSTRUCTIONS:
{style_instructions.get(style, style_instructions["insight"])}

{"PATTERNS FROM TOP-PERFORMING POSTS:" + patterns_analysis if patterns_analysis else ""}

LINKEDIN POST REQUIREMENTS:
1. Maximum 3000 characters (aim for 1200-1500 for optimal engagement)
2. Use line breaks and white space liberally
3. Include 3-5 relevant hashtags
4. No emojis unless absolutely necessary for meaning
5. Write in first person, conversational tone
6. Include a subtle call-to-action
7. The hook (first line) must stop the scroll

OUTPUT FORMAT (respond in valid JSON):
{{
    "content": "The full LinkedIn post text",
    "hook": "Just the first line/hook",
    "post_type": "{style}",
    "estimated_engagement": "low/medium/high",
    "hashtags": ["tag1", "tag2", "tag3"],
    "call_to_action": "The CTA used in the post"
}}

Generate the post now:"""

        try:
            response = self.model.generate_content(prompt)

            # Check if response was blocked by safety filters
            if not response.candidates:
                error_msg = f"No response generated for {style} post - content may have been filtered"
                console.print(f"[yellow]{error_msg}[/yellow]")
                self.errors.append(error_msg)
                return None

            # Check candidate finish reason
            candidate = response.candidates[0]
            if hasattr(candidate, 'finish_reason') and candidate.finish_reason != 1:  # 1 = STOP (normal)
                finish_reasons = {0: "UNSPECIFIED", 1: "STOP", 2: "MAX_TOKENS", 3: "SAFETY", 4: "RECITATION", 5: "OTHER"}
                reason = finish_reasons.get(candidate.finish_reason, str(candidate.finish_reason))
                if candidate.finish_reason == 3:  # SAFETY
                    error_msg = f"Content blocked by safety filter for {style} post"
                    console.print(f"[yellow]{error_msg}[/yellow]")
                    self.errors.append(error_msg)
                    return None

            # Try to get text from response
            try:
                response_text = response.text.strip()
            except ValueError as e:
                error_msg = f"Could not extract text from response for {style} post: {e}"
                console.print(f"[yellow]{error_msg}[/yellow]")
                self.errors.append(error_msg)
                return None

            # Clean up response if it has markdown code blocks
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            data = json.loads(response_text)

            inspiration = []
            if reference_posts:
                inspiration = [p.post_url for p in reference_posts[:3] if p.post_url]

            return GeneratedPost(
                content=data.get("content", ""),
                hook=data.get("hook", ""),
                source_article_title=article.title,
                post_type=data.get("post_type", style),
                estimated_engagement=data.get("estimated_engagement", "medium"),
                hashtags=data.get("hashtags", []),
                call_to_action=data.get("call_to_action", ""),
                inspiration_posts=inspiration
            )

        except json.JSONDecodeError as e:
            error_msg = f"Could not parse JSON response for {style} post: {e}"
            console.print(f"[yellow]{error_msg}[/yellow]")
            self.errors.append(error_msg)
            return None
        except Exception as e:
            error_msg = f"Error generating {style} post: {e}"
            console.print(f"[red]{error_msg}[/red]")
            self.errors.append(error_msg)
            return None

    def get_errors(self) -> list[str]:
        """Return list of errors encountered during generation."""
        return self.errors.copy()

    def clear_errors(self):
        """Clear the error list."""
        self.errors.clear()

    def display_posts(self, posts: list[GeneratedPost] = None):
        """Display generated posts in a formatted way."""
        posts = posts or self.generated_posts

        if not posts:
            console.print("[yellow]No posts to display[/yellow]")
            return

        for i, post in enumerate(posts, 1):
            panel = Panel(
                post.format_for_linkedin(),
                title=f"[bold cyan]Post {i} - {post.post_type.upper()}[/bold cyan]",
                subtitle=f"[dim]Est. engagement: {post.estimated_engagement} | Source: {post.source_article_title}[/dim]",
                border_style="green"
            )
            console.print(panel)
            console.print()


def generate_linkedin_posts(
    article: Article,
    reference_posts: list[LinkedInPost] = None,
    num_posts: int = 5
) -> list[GeneratedPost]:
    """Convenience function to generate LinkedIn posts."""
    generator = PostGenerator()
    return generator.generate_posts_from_article(
        article=article,
        reference_posts=reference_posts,
        num_posts=num_posts
    )


if __name__ == "__main__":
    # Test with a sample article
    from src.article_reader import Article

    test_article = Article(
        title="The Future of AI Agents",
        content="""
        AI agents are transforming how we work. Unlike simple chatbots,
        these autonomous systems can plan, execute, and iterate on complex tasks.

        The key breakthrough is "agentic" behavior - the ability to:
        1. Break down goals into subtasks
        2. Use tools and APIs
        3. Learn from feedback
        4. Operate with minimal human oversight

        This shift from prompt-response to goal-oriented AI will reshape
        every industry. Early adopters are already seeing 10x productivity gains.
        """,
        file_path="test_article.md"
    )

    try:
        generator = PostGenerator()
        posts = generator.generate_posts_from_article(test_article, num_posts=2)
        generator.display_posts(posts)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        console.print("[yellow]Set GEMINI_API_KEY in your .env file to test post generation[/yellow]")
