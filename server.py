#!/usr/bin/env python3
"""Web server entry point for LinkedIn Post Curator."""
import uvicorn

if __name__ == "__main__":
    print("\n" + "="*50)
    print("  LinkedIn Post Curator - Web Interface")
    print("="*50)
    print("\n  Starting server...")
    print("  Open http://localhost:8000 in your browser")
    print("\n  Press Ctrl+C to stop\n")

    uvicorn.run(
        "src.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
