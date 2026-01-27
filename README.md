# LinkedIn Post Curator

An AI-powered tool that helps you create engaging LinkedIn posts by:

1. **Scraping** top-performing LinkedIn posts about AI and automation
2. **Reading** your Substack articles from local markdown/text files
3. **Generating** LinkedIn posts using Google Gemini AI, inspired by what's working
4. **Uploading** generated posts to Google Sheets for scheduling

## Features

- Web scraping of LinkedIn for trending AI/automation content
- Analysis of engagement patterns from successful posts
- Multiple post styles: hook-story, listicle, question, insight, contrarian
- Google Sheets integration for content calendar management
- CLI interface for easy workflow automation

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# LinkedIn (for scraping)
LINKEDIN_EMAIL=your_email@example.com
LINKEDIN_PASSWORD=your_password

# Gemini AI
GEMINI_API_KEY=your_gemini_api_key

# Google Sheets
GOOGLE_CREDENTIALS_PATH=credentials/google_service_account.json
GOOGLE_SHEET_ID=your_sheet_id
```

### 3. Add Your Articles

Place your Substack articles in the `articles/` directory:

```
articles/
├── my-first-article.md
├── ai-automation-tips.txt
└── future-of-work.md
```

### 4. Run the Tool

```bash
# Full workflow (recommended)
python main.py curate

# Or step by step:
python main.py scrape      # Scrape top LinkedIn posts
python main.py articles    # List your articles
python main.py generate    # Generate posts from an article
python main.py sheets      # Check Google Sheets connection
```

## Commands

| Command | Description |
|---------|-------------|
| `curate` | Full workflow: scrape, generate, upload |
| `scrape` | Scrape top AI/automation posts from LinkedIn |
| `articles` | List articles in the articles directory |
| `generate` | Generate LinkedIn posts from an article |
| `sheets` | Test Google Sheets connection |
| `setup` | Display setup instructions |

## Setup Details

### LinkedIn Credentials

The tool uses Selenium to scrape LinkedIn. You need a valid LinkedIn account.

**Note:** LinkedIn may require verification for new login locations. It's recommended to:
- Use your regular LinkedIn account
- Run the tool on a machine where you've logged in before
- Consider using `HEADLESS_BROWSER=false` initially to handle any verification

### Gemini API

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create an API key
3. Add it to your `.env` file

### Google Sheets

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project and enable Google Sheets API
3. Create a Service Account and download JSON credentials
4. Save credentials to `credentials/google_service_account.json`
5. Create a Google Sheet and share it with the service account email
6. Copy the Sheet ID to your `.env` file

Run `python main.py setup` for detailed instructions.

## Project Structure

```
LinkedIn-Automation/
├── main.py                 # CLI entry point
├── requirements.txt        # Python dependencies
├── .env.example           # Environment template
├── .gitignore
├── articles/              # Your Substack articles go here
├── credentials/           # Google service account JSON
├── cache/                 # Cached scraped posts
└── src/
    ├── config.py          # Configuration management
    ├── linkedin_scraper.py # LinkedIn web scraper
    ├── article_reader.py   # Local article reader
    ├── post_generator.py   # Gemini-powered post generator
    └── sheets_uploader.py  # Google Sheets integration
```

## Generated Post Styles

The tool generates posts in these styles:

- **Hook-Story**: Strong opening hook + personal narrative
- **Listicle**: Numbered list with actionable items
- **Question**: Opens with thought-provoking question
- **Insight**: Shares counterintuitive insight
- **Contrarian**: Challenges conventional wisdom

## Tips for Best Results

1. **Quality articles**: The better your source content, the better the generated posts
2. **Fresh scrapes**: Run `scrape` weekly to keep inspiration posts current
3. **Edit before posting**: Generated posts are drafts - personalize them
4. **Track engagement**: Use the Status column in Sheets to track what works

## Legal Considerations

- Web scraping LinkedIn may violate their Terms of Service
- Use responsibly and consider rate limits
- This tool is for personal productivity, not spam

## License

MIT
