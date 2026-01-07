import os

import uvicorn
from dotenv import load_dotenv


def run():
    """
    Entrypoint to launch the FastAPI app via uvicorn.

    Environment variables:
    - HOST: bind address (default "0.0.0.0")
    - PORT: bind port (default 8000)
    - RELOAD: enable auto-reload (set to "true" to enable; default off)
    """
    load_dotenv()  # pick up .env before reading config

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "false").lower() == "true"

    uvicorn.run("api:api", host=host, port=port, reload=reload)


if __name__ == "__main__":
    run()

