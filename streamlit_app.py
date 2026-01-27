"""Streamlit Web App for LinkedIn Post Curator - Cloud Compatible."""
import os
import sys
import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass

import streamlit as st

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.article_reader import ArticleReader

# Try to import config, fall back to st.secrets for cloud
try:
    from src.config import ARTICLES_DIR
except:
    ARTICLES_DIR = Path(__file__).parent / "articles"
    ARTICLES_DIR.mkdir(exist_ok=True)

# Get API key from secrets (cloud) or environment (local)
def get_gemini_api_key():
    """Get Gemini API key from Streamlit secrets or environment."""
    try:
        return st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""))
    except:
        return os.getenv("GEMINI_API_KEY", "")

GEMINI_API_KEY = get_gemini_api_key()

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


@dataclass
class SamplePost:
    """Represents a sample LinkedIn post for inspiration."""
    author_name: str
    author_headline: str
    content: str
    engagement_score: int
    likes_count: int
    comments_count: int
    post_type: str


def init_session_state():
    """Initialize session state variables."""
    if 'generated_posts' not in st.session_state:
        st.session_state.generated_posts = []
    if 'custom_posts' not in st.session_state:
        st.session_state.custom_posts = []
    if 'inspiration_posts' not in st.session_state:
        st.session_state.inspiration_posts = []


def load_articles():
    """Load all articles from the articles directory."""
    reader = ArticleReader()
    return reader.read_directory()


def load_sample_posts():
    """Load sample posts from JSON file."""
    sample_file = Path(__file__).parent / "data" / "sample_posts.json"

    if sample_file.exists():
        try:
            with open(sample_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            posts = []
            for p in data.get("sample_posts", []):
                posts.append(SamplePost(
                    author_name=p.get("author_name", "Unknown"),
                    author_headline=p.get("author_headline", ""),
                    content=p.get("content", ""),
                    engagement_score=p.get("engagement_score", 0),
                    likes_count=p.get("likes_count", 0),
                    comments_count=p.get("comments_count", 0),
                    post_type=p.get("post_type", "insight")
                ))
            return posts, data.get("trending_themes", [])
        except Exception as e:
            st.error(f"Error loading sample posts: {e}")
            return [], []
    return [], []


def get_all_inspiration_posts():
    """Get all inspiration posts (sample + custom)."""
    sample_posts, _ = load_sample_posts()
    custom_posts = st.session_state.get('custom_posts', [])
    return sample_posts + custom_posts


# ============ PAGES ============

def content_ideas_page():
    """Content Ideas page - show trending themes and patterns."""
    st.markdown('<p class="main-header">Content Ideas</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Discover trending themes and hook patterns from top LinkedIn posts</p>', unsafe_allow_html=True)

    # Load sample posts
    posts, themes = load_sample_posts()
    custom_posts = st.session_state.get('custom_posts', [])
    all_posts = posts + custom_posts

    if not all_posts:
        st.warning("No inspiration posts available. Go to **Inspiration Posts** to add some.")
        return

    # Display trending themes
    if themes:
        st.subheader("Trending Themes")
        theme_cols = st.columns(min(len(themes), 4))
        for i, theme in enumerate(themes[:8]):
            with theme_cols[i % len(theme_cols)]:
                st.info(f"**{theme}**")

    st.divider()

    # Display top post patterns
    st.subheader("Top Hook Patterns")
    st.caption("Learn from these high-engagement opening lines")

    for i, post in enumerate(all_posts[:8]):
        hook = post.content.split('\n')[0][:150]

        # Determine format type and color
        if post.post_type == "listicle":
            format_type = "Listicle"
            color = "#057642"
        elif post.post_type == "question":
            format_type = "Question"
            color = "#b24020"
        elif post.post_type == "contrarian":
            format_type = "Contrarian"
            color = "#7c3aed"
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
        st.error("""
        **Gemini API key not configured.**

        Add `GEMINI_API_KEY` to your Streamlit secrets or `.env` file.

        Get your key from: https://makersuite.google.com/app/apikey
        """)
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
        inspiration_posts = get_all_inspiration_posts()
        use_inspiration = st.checkbox(
            f"Use inspiration posts ({len(inspiration_posts)} available)",
            value=len(inspiration_posts) > 0
        )

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
                # Import here to avoid issues if not installed
                from src.post_generator import PostGenerator

                # Prepare reference posts for inspiration
                reference_posts = None
                if use_inspiration and inspiration_posts:
                    # Convert to format expected by generator
                    from src.linkedin_scraper import LinkedInPost
                    reference_posts = []
                    for p in inspiration_posts[:10]:
                        ref_post = LinkedInPost(
                            author_name=p.author_name,
                            author_headline=p.author_headline,
                            author_profile_url="",
                            content=p.content,
                            post_url="",
                            likes_count=p.likes_count,
                            comments_count=p.comments_count,
                            reposts_count=0,
                            engagement_score=p.engagement_score
                        )
                        reference_posts.append(ref_post)

                # Generate posts
                generator = PostGenerator()
                posts = generator.generate_posts_from_article(
                    article=selected_article,
                    reference_posts=reference_posts,
                    num_posts=num_posts
                )

                st.session_state.generated_posts = posts

                if len(posts) > 0:
                    st.success(f"Generated {len(posts)} posts!")
                else:
                    # Show errors if no posts were generated
                    errors = generator.get_errors()
                    if errors:
                        st.error(f"Failed to generate posts. {len(errors)} error(s) occurred:")
                        for err in errors:
                            st.warning(f"- {err}")
                        st.info("This may be due to content safety filters. Try adjusting your article content or try again.")
                    else:
                        st.warning("No posts were generated. Please try again or check your article content.")

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
                        st.info("Copy the text above")

                # Content
                st.markdown(f"""
                <div class="post-card">
                    {post.content.replace(chr(10), '<br>')}
                    <br><br>
                    <span style="color: #0a66c2;">{' '.join(f'#{tag}' for tag in post.hashtags)}</span>
                </div>
                """, unsafe_allow_html=True)

            st.divider()


def inspiration_posts_page():
    """Inspiration Posts page - manage sample and custom posts."""
    st.markdown('<p class="main-header">Inspiration Posts</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">View sample posts and add your own LinkedIn posts for inspiration</p>', unsafe_allow_html=True)

    # Tabs for sample vs custom
    tab1, tab2 = st.tabs(["Sample Posts", "Add Your Own"])

    with tab1:
        st.subheader("Pre-loaded Sample Posts")
        st.caption("High-performing AI & automation posts for inspiration")

        posts, themes = load_sample_posts()

        if not posts:
            st.warning("No sample posts found. Check data/sample_posts.json")
        else:
            # Summary metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                avg_engagement = sum(p.engagement_score for p in posts) / len(posts)
                st.metric("Avg Engagement", f"{avg_engagement:.0f}")
            with col2:
                total_likes = sum(p.likes_count for p in posts)
                st.metric("Total Likes", f"{total_likes:,}")
            with col3:
                st.metric("Sample Posts", len(posts))

            st.divider()

            # Post list
            for i, post in enumerate(posts):
                with st.expander(f"{post.author_name} - Engagement: {post.engagement_score}"):
                    st.markdown(f"**{post.author_headline}**")
                    st.markdown(post.content)

                    col1, col2 = st.columns(2)
                    with col1:
                        st.caption(f"Likes: {post.likes_count}")
                    with col2:
                        st.caption(f"Type: {post.post_type}")

    with tab2:
        st.subheader("Add Custom LinkedIn Posts")
        st.caption("Paste LinkedIn posts you find inspiring to use as reference")

        with st.form("add_custom_post"):
            author = st.text_input("Author Name", placeholder="e.g., John Smith")
            headline = st.text_input("Author Headline", placeholder="e.g., AI Consultant")
            content = st.text_area("Post Content", height=200, placeholder="Paste the LinkedIn post content here...")

            post_type = st.selectbox("Post Type", ["hook-story", "listicle", "question", "insight", "contrarian"])

            col1, col2 = st.columns(2)
            with col1:
                engagement = st.number_input("Engagement Score (estimate)", min_value=0, value=500)
            with col2:
                likes = st.number_input("Likes (estimate)", min_value=0, value=300)

            submitted = st.form_submit_button("Add Post", type="primary")

            if submitted and content:
                new_post = SamplePost(
                    author_name=author or "Anonymous",
                    author_headline=headline or "",
                    content=content,
                    engagement_score=engagement,
                    likes_count=likes,
                    comments_count=0,
                    post_type=post_type
                )

                if 'custom_posts' not in st.session_state:
                    st.session_state.custom_posts = []
                st.session_state.custom_posts.append(new_post)
                st.success("Post added to your inspiration collection!")
                st.rerun()

        # Show custom posts
        if st.session_state.get('custom_posts'):
            st.divider()
            st.subheader(f"Your Custom Posts ({len(st.session_state.custom_posts)})")

            for i, post in enumerate(st.session_state.custom_posts):
                with st.expander(f"{post.author_name} - {post.post_type}"):
                    st.markdown(post.content[:300] + "..." if len(post.content) > 300 else post.content)
                    if st.button("Remove", key=f"remove_custom_{i}"):
                        st.session_state.custom_posts.pop(i)
                        st.rerun()


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
            ["Content Ideas", "My Articles", "Generate Posts", "Inspiration Posts"],
            label_visibility="collapsed"
        )

        st.divider()

        # Status indicators
        st.markdown("### Status")

        articles = load_articles()
        st.markdown(f"**Articles:** {len(articles)}")

        sample_posts, _ = load_sample_posts()
        custom_posts = len(st.session_state.get('custom_posts', []))
        st.markdown(f"**Inspiration Posts:** {len(sample_posts) + custom_posts}")

        if GEMINI_API_KEY:
            st.success("Gemini API: Configured")
        else:
            st.error("Gemini API: Not set")

        st.divider()
        st.caption("☁️ Cloud-ready version")

    # Main content
    if page == "Content Ideas":
        content_ideas_page()
    elif page == "My Articles":
        my_articles_page()
    elif page == "Generate Posts":
        generate_posts_page()
    elif page == "Inspiration Posts":
        inspiration_posts_page()


if __name__ == "__main__":
    main()
