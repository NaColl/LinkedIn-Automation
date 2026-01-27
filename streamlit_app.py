"""Streamlit Web App for LinkedIn Post Curator."""
import os
import sys
from pathlib import Path
from datetime import datetime

import streamlit as st

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import ARTICLES_DIR, GEMINI_API_KEY, LINKEDIN_EMAIL
from src.linkedin_scraper import LinkedInScraper
from src.article_reader import ArticleReader
from src.post_generator import PostGenerator

# Page config
st.set_page_config(
    page_title="LinkedIn Post Curator",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #0a66c2;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        color: #666;
        margin-bottom: 2rem;
    }
    .post-card {
        background: #f8f9fa;
        border-radius: 10px;
        padding: 1.5rem;
        margin: 1rem 0;
        border-left: 4px solid #0a66c2;
    }
    .idea-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 10px;
        padding: 1.5rem;
        margin: 0.5rem 0;
    }
    .metric-card {
        background: #e7f3ff;
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
    }
    .stButton>button {
        background-color: #0a66c2;
        color: white;
        border-radius: 20px;
        padding: 0.5rem 2rem;
        border: none;
    }
    .stButton>button:hover {
        background-color: #004182;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Initialize session state variables."""
    if 'generated_posts' not in st.session_state:
        st.session_state.generated_posts = []
    if 'cached_linkedin_posts' not in st.session_state:
        st.session_state.cached_linkedin_posts = []
    if 'scraping_in_progress' not in st.session_state:
        st.session_state.scraping_in_progress = False


def load_articles():
    """Load all articles from the articles directory."""
    reader = ArticleReader()
    return reader.read_directory()


def load_cached_linkedin_posts():
    """Load cached LinkedIn posts."""
    scraper = LinkedInScraper()
    posts = scraper.load_cache(max_age_hours=168)  # 1 week
    return posts


# ============ PAGES ============

def content_ideas_page():
    """Content Ideas page - show trending themes and patterns."""
    st.markdown('<p class="main-header">Content Ideas</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Discover trending themes and hook patterns from top LinkedIn posts</p>', unsafe_allow_html=True)

    # Load cached posts
    posts = load_cached_linkedin_posts()

    if not posts:
        st.warning("No LinkedIn posts cached yet. Go to **LinkedIn Scanner** to scrape top posts first.")
        if st.button("Go to LinkedIn Scanner"):
            st.session_state.page = "LinkedIn Scanner"
            st.rerun()
        return

    # Extract themes
    themes = set()
    for post in posts[:20]:
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
        if 'chatgpt' in content_lower or 'gpt' in content_lower:
            themes.add('ChatGPT/GPT')
        if 'prompt' in content_lower:
            themes.add('Prompting')

    # Display trending themes
    st.subheader("Trending Themes")
    theme_cols = st.columns(len(themes) if themes else 1)
    for i, theme in enumerate(list(themes)):
        with theme_cols[i % len(theme_cols)]:
            st.info(f"**{theme}**")

    st.divider()

    # Display top post patterns
    st.subheader("Top Hook Patterns")
    st.caption("Learn from these high-engagement opening lines")

    for i, post in enumerate(posts[:6]):
        hook = post.content.split('\n')[0][:150]

        # Determine format type
        if any(char.isdigit() for char in post.content[:50]):
            format_type = "Listicle"
            color = "#057642"
        elif '?' in post.content[:100]:
            format_type = "Question"
            color = "#b24020"
        else:
            format_type = "Story/Insight"
            color = "#0a66c2"

        with st.container():
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, {color}22 0%, {color}11 100%);
                            border-left: 4px solid {color}; border-radius: 8px; padding: 1rem; margin: 0.5rem 0;">
                    <p style="font-style: italic; margin-bottom: 0.5rem;">"{hook}..."</p>
                    <small style="color: #666;">by {post.author_name} | Format: {format_type}</small>
                </div>
                """, unsafe_allow_html=True)
            with col2:
                st.metric("Engagement", post.engagement_score)


def my_articles_page():
    """My Articles page - manage Substack articles."""
    st.markdown('<p class="main-header">My Articles</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Manage your Substack articles for LinkedIn post generation</p>', unsafe_allow_html=True)

    # Create new article section
    with st.expander("Create New Article", expanded=False):
        new_title = st.text_input("Article Title", key="new_title")
        new_content = st.text_area("Article Content (Markdown supported)", height=300, key="new_content")

        if st.button("Save Article", type="primary"):
            if new_title and new_content:
                # Generate filename
                safe_title = "".join(c if c.isalnum() or c in " -_" else "" for c in new_title)
                safe_title = safe_title.replace(" ", "-").lower()[:50]
                filename = f"{safe_title}.md"
                file_path = ARTICLES_DIR / filename

                if file_path.exists():
                    st.error("An article with this name already exists!")
                else:
                    content = f"# {new_title}\n\n{new_content}"
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    st.success(f"Article saved as {filename}")
                    st.rerun()
            else:
                st.error("Please fill in both title and content")

    st.divider()

    # List existing articles
    articles = load_articles()

    if not articles:
        st.info("No articles found. Create your first article above!")
        return

    st.subheader(f"Your Articles ({len(articles)})")

    for article in articles:
        with st.container():
            col1, col2, col3 = st.columns([3, 1, 1])

            with col1:
                st.markdown(f"**{article.title}**")
                st.caption(f"{article.word_count} words | {Path(article.file_path).name}")

            with col2:
                if st.button("Edit", key=f"edit_{article.file_path}"):
                    st.session_state.editing_article = article.file_path
                    st.rerun()

            with col3:
                if st.button("Delete", key=f"del_{article.file_path}"):
                    os.remove(article.file_path)
                    st.success("Article deleted")
                    st.rerun()

        st.divider()

    # Edit modal
    if 'editing_article' in st.session_state and st.session_state.editing_article:
        file_path = st.session_state.editing_article
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        st.subheader("Edit Article")
        edited_content = st.text_area("Content", value=content, height=400, key="edit_content")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Save Changes", type="primary"):
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(edited_content)
                st.session_state.editing_article = None
                st.success("Article updated!")
                st.rerun()
        with col2:
            if st.button("Cancel"):
                st.session_state.editing_article = None
                st.rerun()


def generate_posts_page():
    """Generate Posts page - create LinkedIn posts from articles."""
    st.markdown('<p class="main-header">Generate LinkedIn Posts</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Transform your articles into engaging LinkedIn content using AI</p>', unsafe_allow_html=True)

    # Check Gemini API
    if not GEMINI_API_KEY:
        st.error("Gemini API key not configured. Please add GEMINI_API_KEY to your .env file.")
        return

    # Load articles
    articles = load_articles()

    if not articles:
        st.warning("No articles found. Go to **My Articles** to create one first.")
        return

    # Configuration
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Configuration")

        # Article selection
        article_options = {a.title: a for a in articles}
        selected_title = st.selectbox("Select Article", options=list(article_options.keys()))
        selected_article = article_options[selected_title]

        # Number of posts
        num_posts = st.slider("Number of posts to generate", min_value=1, max_value=10, value=5)

        # Use inspiration
        use_inspiration = st.checkbox("Use top LinkedIn posts as inspiration", value=True)

        # Post styles
        st.caption("Post styles that will be generated:")
        styles_col1, styles_col2 = st.columns(2)
        with styles_col1:
            st.markdown("- **Hook-Story**: Attention-grabbing hook + narrative")
            st.markdown("- **Listicle**: Numbered actionable items")
            st.markdown("- **Question**: Thought-provoking opener")
        with styles_col2:
            st.markdown("- **Insight**: Counterintuitive findings")
            st.markdown("- **Contrarian**: Challenge conventional wisdom")

    with col2:
        st.subheader("Article Preview")
        with st.container(height=300):
            st.markdown(f"**{selected_article.title}**")
            st.caption(f"{selected_article.word_count} words")
            st.markdown(selected_article.content[:1000] + "..." if len(selected_article.content) > 1000 else selected_article.content)

    st.divider()

    # Generate button
    if st.button("Generate Posts", type="primary", use_container_width=True):
        with st.spinner("Generating LinkedIn posts with Gemini AI..."):
            try:
                # Load reference posts if requested
                reference_posts = None
                if use_inspiration:
                    reference_posts = load_cached_linkedin_posts()

                # Generate posts
                generator = PostGenerator()
                posts = generator.generate_posts_from_article(
                    article=selected_article,
                    reference_posts=reference_posts,
                    num_posts=num_posts
                )

                st.session_state.generated_posts = posts
                st.success(f"Generated {len(posts)} posts!")

            except Exception as e:
                st.error(f"Error generating posts: {str(e)}")

    # Display generated posts
    if st.session_state.generated_posts:
        st.subheader("Generated Posts")

        for i, post in enumerate(st.session_state.generated_posts):
            with st.container():
                # Header
                col1, col2, col3 = st.columns([2, 2, 1])
                with col1:
                    st.markdown(f"**Post {i+1}** - {post.post_type.upper()}")
                with col2:
                    st.caption(f"Est. engagement: {post.estimated_engagement}")
                with col3:
                    if st.button("Copy", key=f"copy_{i}"):
                        full_text = post.content + "\n\n" + " ".join(f"#{tag}" for tag in post.hashtags)
                        st.code(full_text, language=None)
                        st.info("Text shown above - copy it manually (Streamlit clipboard not supported in all browsers)")

                # Content
                st.markdown(f"""
                <div class="post-card">
                    {post.content.replace(chr(10), '<br>')}
                    <br><br>
                    <span style="color: #0a66c2;">{' '.join(f'#{tag}' for tag in post.hashtags)}</span>
                </div>
                """, unsafe_allow_html=True)

            st.divider()


def linkedin_scanner_page():
    """LinkedIn Scanner page - scrape top posts using headless browser."""
    st.markdown('<p class="main-header">LinkedIn Scanner</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Scrape top-performing AI & automation posts using headless browser</p>', unsafe_allow_html=True)

    # Check LinkedIn credentials
    if not LINKEDIN_EMAIL:
        st.warning("""
        **LinkedIn credentials not configured.**

        To enable scraping, add these to your `.env` file:
        ```
        LINKEDIN_EMAIL=your_email@example.com
        LINKEDIN_PASSWORD=your_password
        ```
        """)

    # Scan button
    col1, col2 = st.columns([1, 2])
    with col1:
        if st.button("Scan LinkedIn", type="primary", disabled=not LINKEDIN_EMAIL):
            st.session_state.scraping_in_progress = True

            progress_bar = st.progress(0)
            status_text = st.empty()

            try:
                status_text.text("Initializing headless browser...")
                progress_bar.progress(10)

                scraper = LinkedInScraper()

                status_text.text("Logging in to LinkedIn...")
                progress_bar.progress(30)

                posts = scraper.fetch_top_posts()

                progress_bar.progress(100)
                status_text.text(f"Done! Found {len(posts)} posts.")

                st.session_state.cached_linkedin_posts = posts
                st.success(f"Successfully scraped {len(posts)} posts!")

            except Exception as e:
                st.error(f"Scraping failed: {str(e)}")
            finally:
                st.session_state.scraping_in_progress = False

    with col2:
        st.caption("This uses Selenium with a headless Chrome browser to scrape LinkedIn search results for AI/automation posts.")

    st.divider()

    # Display cached posts
    posts = load_cached_linkedin_posts()

    if posts:
        st.subheader(f"Cached Posts ({len(posts)})")
        st.caption("Posts are cached for 7 days")

        # Summary metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            avg_engagement = sum(p.engagement_score for p in posts) / len(posts) if posts else 0
            st.metric("Avg Engagement", f"{avg_engagement:.0f}")
        with col2:
            total_likes = sum(p.likes_count for p in posts)
            st.metric("Total Likes", f"{total_likes:,}")
        with col3:
            st.metric("Posts Cached", len(posts))

        st.divider()

        # Post list
        for i, post in enumerate(posts[:15]):
            with st.expander(f"{post.author_name} - Engagement: {post.engagement_score}"):
                st.markdown(f"**{post.author_headline}**")
                st.markdown(post.content[:500] + "..." if len(post.content) > 500 else post.content)

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.caption(f"Likes: {post.likes_count}")
                with col2:
                    st.caption(f"Comments: {post.comments_count}")
                with col3:
                    st.caption(f"Reposts: {post.reposts_count}")
    else:
        st.info("No cached posts. Click 'Scan LinkedIn' to fetch top posts.")


# ============ MAIN APP ============

def main():
    """Main application."""
    init_session_state()

    # Sidebar navigation
    with st.sidebar:
        st.markdown("## LinkedIn Post Curator")
        st.caption("AI-powered content creation")

        st.divider()

        page = st.radio(
            "Navigation",
            ["Content Ideas", "My Articles", "Generate Posts", "LinkedIn Scanner"],
            label_visibility="collapsed"
        )

        st.divider()

        # Status indicators
        st.markdown("### Status")

        articles = load_articles()
        st.markdown(f"**Articles:** {len(articles)}")

        posts = load_cached_linkedin_posts()
        st.markdown(f"**Cached Posts:** {len(posts)}")

        if GEMINI_API_KEY:
            st.success("Gemini API: Configured")
        else:
            st.error("Gemini API: Not set")

        if LINKEDIN_EMAIL:
            st.success("LinkedIn: Configured")
        else:
            st.warning("LinkedIn: Not set")

    # Main content
    if page == "Content Ideas":
        content_ideas_page()
    elif page == "My Articles":
        my_articles_page()
    elif page == "Generate Posts":
        generate_posts_page()
    elif page == "LinkedIn Scanner":
        linkedin_scanner_page()


if __name__ == "__main__":
    main()
