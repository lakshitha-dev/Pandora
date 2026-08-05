"""Local dev entrypoint — use this on Windows.

    python run.py                 # → http://localhost:5000/docs

Why not `uvicorn app.main:app --reload`? psycopg's async mode cannot run on
Windows' default ProactorEventLoop, and by the time uvicorn imports `app.main`
the loop already exists — setting the policy from inside the app is too late.
This script sets it first, then starts the server.

On Linux (Azure App Service) the plain uvicorn command is fine; the startup
command in infra/ uses it.
"""

import asyncio
import sys

import uvicorn

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

if __name__ == "__main__":
    from app.core.config import get_settings

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=5000,
        reload=True,
        log_level=settings.log_level.lower(),
    )
