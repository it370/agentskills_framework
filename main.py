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
    - DEFAULT_USER_ID: default user for credential access (default "system")
    """
    load_dotenv()  # pick up .env before reading config
    
    # Initialize global auth context for credential access
    try:
        from services.credentials import AuthContext
        auth = AuthContext.initialize_from_env()
        print(f"[AUTH] Initialized global auth context for user: {auth.get_current_user().user_id}")
    except Exception as e:
        print(f"[AUTH] Warning: Could not initialize auth context: {e}")
        print("[AUTH] Credential-based skills may not work without user_context in inputs")

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "false").lower() == "true"

    uvicorn.run("api:api", host=host, port=port, reload=reload)


if __name__ == "__main__":
    run()

