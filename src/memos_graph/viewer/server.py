"""memos-graph viewer UI server."""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse
from pathlib import Path
import uvicorn


def create_viewer_app() -> FastAPI:
    """Create viewer FastAPI application."""
    app = FastAPI(title="memos-graph Viewer")

    static_dir = Path(__file__).parent
    index_html = static_dir / "index.html"

    @app.get("/", response_class=HTMLResponse)
    async def root():
        """Serve the main viewer page."""
        return FileResponse(index_html)

    @app.get("/viewer", response_class=HTMLResponse)
    async def viewer():
        """Alias for viewer root."""
        return FileResponse(index_html)

    return app


def run_viewer(host: str = "0.0.0.0", port: int = 8080):
    """Run the viewer server."""
    app = create_viewer_app()
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_viewer()
