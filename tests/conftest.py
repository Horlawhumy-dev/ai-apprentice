from app.core.config import settings
from app.db.init_db import init_db

# Keep tests deterministic and offline: force the deterministic question policy.
settings.llm_api_key = ""

init_db()
