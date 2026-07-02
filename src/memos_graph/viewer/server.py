"""memos-graph viewer UI server."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pathlib import Path
import uvicorn


def create_viewer_app() -> FastAPI:
    """Create viewer FastAPI application."""
    app = FastAPI(title="memos-graph Viewer")

    # Serve static files (CSS, JS)
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def root():
        """Serve the main viewer page."""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>memos-graph Viewer</title>
            <style>
                body { font-family: system-ui, sans-serif; margin: 2rem; }
                h1 { color: #333; }
                .status { padding: 1rem; background: #f0f0f0; border-radius: 8px; }
            </style>
        </head>
        <body>
            <h1>memos-graph Viewer</h1>
            <div class="status">
                <p>Viewer is running. Full UI coming soon...</p>
                <p>API: <a href="/api/v1/health">/api/v1/health</a></p>
            </div>
        </body>
        </html>
        """

    return app


def run_viewer(host: str = "127.0.0.1", port: int = 8080):
    """Run the viewer server."""
    app = create_viewer_app()
    uvicorn.run(app, host=host, port=port)
