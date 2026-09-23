import os

import uvicorn

from webhook_lab.app import create_app
from webhook_lab.config import Settings

settings = Settings.from_env()
host = os.getenv("WLAB_HOST", "127.0.0.1")
port = int(os.getenv("WLAB_PORT", "8000"))
print(f"Webhook Lab: http://127.0.0.1:{port}")
print("Paste the token from WLAB_ADMIN_TOKEN or data/admin.token into the workbench.")
uvicorn.run(create_app(settings), host=host, port=port, access_log=False)
