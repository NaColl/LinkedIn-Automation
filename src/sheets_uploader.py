"""Google Sheets integration for uploading generated LinkedIn posts."""
from datetime import datetime
from pathlib import Path
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials
from rich.console import Console
from rich.table import Table

from src.config import GOOGLE_CREDENTIALS_PATH, GOOGLE_SHEET_ID, GOOGLE_WORKSHEET_NAME
from src.post_generator import GeneratedPost

console = Console()

# Google Sheets API scopes
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]


class SheetsUploader:
    """Uploads generated posts to Google Sheets."""

    # Column headers for the sheet
    HEADERS = [
        "Generated At",
        "Post Type",
        "Hook",
        "Full Post",
        "Source Article",
        "Hashtags",
        "Est. Engagement",
        "Call to Action",
        "Status",
        "Notes"
    ]

    def __init__(self, credentials_path: str = None, sheet_id: str = None):
        self.credentials_path = credentials_path or GOOGLE_CREDENTIALS_PATH
        self.sheet_id = sheet_id or GOOGLE_SHEET_ID
        self.worksheet_name = GOOGLE_WORKSHEET_NAME
        self.client: Optional[gspread.Client] = None
        self.sheet: Optional[gspread.Spreadsheet] = None
        self.worksheet: Optional[gspread.Worksheet] = None

    def _authenticate(self) -> bool:
        """Authenticate with Google Sheets API."""
        creds_path = Path(self.credentials_path)

        if not creds_path.exists():
            console.print(f"[red]Credentials file not found: {creds_path}[/red]")
            console.print("[yellow]To set up Google Sheets integration:[/yellow]")
            console.print("1. Go to Google Cloud Console")
            console.print("2. Create a Service Account")
            console.print("3. Download the JSON credentials")
            console.print(f"4. Save it to: {creds_path}")
            console.print("5. Share your Google Sheet with the service account email")
            return False

        try:
            credentials = Credentials.from_service_account_file(
                str(creds_path),
                scopes=SCOPES
            )
            self.client = gspread.authorize(credentials)
            console.print("[green]Successfully authenticated with Google Sheets[/green]")
            return True

        except Exception as e:
            console.print(f"[red]Authentication failed: {e}[/red]")
            return False

    def _get_or_create_worksheet(self) -> bool:
        """Get or create the worksheet."""
        if not self.sheet_id:
            console.print("[red]GOOGLE_SHEET_ID not set in environment[/red]")
            return False

        try:
            self.sheet = self.client.open_by_key(self.sheet_id)
            console.print(f"[green]Opened sheet: {self.sheet.title}[/green]")

            # Try to get existing worksheet
            try:
                self.worksheet = self.sheet.worksheet(self.worksheet_name)
                console.print(f"[green]Using worksheet: {self.worksheet_name}[/green]")
            except gspread.WorksheetNotFound:
                # Create new worksheet
                self.worksheet = self.sheet.add_worksheet(
                    title=self.worksheet_name,
                    rows=1000,
                    cols=len(self.HEADERS)
                )
                console.print(f"[green]Created worksheet: {self.worksheet_name}[/green]")
                # Add headers
                self.worksheet.append_row(self.HEADERS)

            return True

        except gspread.SpreadsheetNotFound:
            console.print(f"[red]Spreadsheet not found with ID: {self.sheet_id}[/red]")
            console.print("[yellow]Make sure to share the sheet with your service account email[/yellow]")
            return False
        except Exception as e:
            console.print(f"[red]Error accessing sheet: {e}[/red]")
            return False

    def connect(self) -> bool:
        """Connect to Google Sheets."""
        if not self._authenticate():
            return False
        if not self._get_or_create_worksheet():
            return False
        return True

    def _ensure_headers(self):
        """Ensure headers exist in the worksheet."""
        try:
            first_row = self.worksheet.row_values(1)
            if not first_row or first_row != self.HEADERS:
                # Insert headers at the top
                if not first_row:
                    self.worksheet.append_row(self.HEADERS)
                else:
                    self.worksheet.insert_row(self.HEADERS, 1)
        except Exception:
            self.worksheet.append_row(self.HEADERS)

    def _post_to_row(self, post: GeneratedPost) -> list:
        """Convert a GeneratedPost to a row of values."""
        return [
            post.generated_at.strftime("%Y-%m-%d %H:%M"),
            post.post_type,
            post.hook[:100] + "..." if len(post.hook) > 100 else post.hook,
            post.content,
            post.source_article_title,
            ", ".join(post.hashtags),
            post.estimated_engagement,
            post.call_to_action,
            "Draft",  # Status column for tracking
            ""  # Notes column
        ]

    def upload_posts(self, posts: list[GeneratedPost]) -> int:
        """Upload multiple posts to the sheet."""
        if not self.worksheet:
            if not self.connect():
                return 0

        self._ensure_headers()

        uploaded = 0
        rows_to_add = []

        for post in posts:
            row = self._post_to_row(post)
            rows_to_add.append(row)

        if rows_to_add:
            try:
                self.worksheet.append_rows(rows_to_add)
                uploaded = len(rows_to_add)
                console.print(f"[green]Uploaded {uploaded} posts to Google Sheets[/green]")
            except Exception as e:
                console.print(f"[red]Error uploading posts: {e}[/red]")

        return uploaded

    def upload_post(self, post: GeneratedPost) -> bool:
        """Upload a single post to the sheet."""
        return self.upload_posts([post]) == 1

    def get_all_posts(self) -> list[dict]:
        """Retrieve all posts from the sheet."""
        if not self.worksheet:
            if not self.connect():
                return []

        try:
            records = self.worksheet.get_all_records()
            return records
        except Exception as e:
            console.print(f"[red]Error retrieving posts: {e}[/red]")
            return []

    def display_sheet_summary(self):
        """Display a summary of posts in the sheet."""
        posts = self.get_all_posts()

        if not posts:
            console.print("[yellow]No posts found in the sheet[/yellow]")
            return

        table = Table(title=f"Posts in '{self.worksheet_name}'")
        table.add_column("Date", style="dim")
        table.add_column("Type")
        table.add_column("Hook", max_width=40)
        table.add_column("Status")
        table.add_column("Engagement")

        for post in posts[-10:]:  # Show last 10
            table.add_row(
                post.get("Generated At", ""),
                post.get("Post Type", ""),
                post.get("Hook", "")[:40],
                post.get("Status", ""),
                post.get("Est. Engagement", "")
            )

        console.print(table)
        console.print(f"[dim]Total posts: {len(posts)}[/dim]")


def upload_to_sheets(posts: list[GeneratedPost]) -> int:
    """Convenience function to upload posts to Google Sheets."""
    uploader = SheetsUploader()
    return uploader.upload_posts(posts)


def create_sheet_template():
    """Create a template for the Google Sheet setup instructions."""
    instructions = """
# Google Sheets Setup Instructions

## Step 1: Create a Google Cloud Project
1. Go to https://console.cloud.google.com/
2. Create a new project or select an existing one
3. Enable the Google Sheets API and Google Drive API

## Step 2: Create a Service Account
1. Go to "IAM & Admin" > "Service Accounts"
2. Click "Create Service Account"
3. Give it a name like "linkedin-automation"
4. Click "Create and Continue"
5. Skip the optional steps and click "Done"

## Step 3: Create Credentials
1. Click on your new service account
2. Go to the "Keys" tab
3. Click "Add Key" > "Create new key"
4. Choose JSON format
5. Download the file and save it to: credentials/google_service_account.json

## Step 4: Create Your Google Sheet
1. Go to https://sheets.google.com/
2. Create a new spreadsheet
3. Name it (e.g., "LinkedIn Posts")
4. Copy the Sheet ID from the URL:
   https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit

## Step 5: Share the Sheet
1. Open your service account JSON file
2. Find the "client_email" field
3. Share your Google Sheet with this email address
4. Give it "Editor" permissions

## Step 6: Update Your .env File
```
GOOGLE_CREDENTIALS_PATH=credentials/google_service_account.json
GOOGLE_SHEET_ID=your_sheet_id_here
GOOGLE_WORKSHEET_NAME=LinkedIn Posts
```

## Testing
Run: python -c "from src.sheets_uploader import SheetsUploader; s = SheetsUploader(); s.connect()"
"""
    return instructions


if __name__ == "__main__":
    console.print("[bold]Google Sheets Integration Test[/bold]\n")

    # Check if credentials exist
    creds_path = Path(GOOGLE_CREDENTIALS_PATH)
    if not creds_path.exists():
        console.print("[yellow]Credentials not found. Here's how to set up:[/yellow]\n")
        console.print(create_sheet_template())
    else:
        uploader = SheetsUploader()
        if uploader.connect():
            uploader.display_sheet_summary()
        else:
            console.print("[red]Failed to connect to Google Sheets[/red]")
