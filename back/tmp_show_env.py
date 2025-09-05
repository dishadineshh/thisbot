from dotenv import load_dotenv
import os
load_dotenv()
def show(k): print(f"{k} = {os.getenv(k)}" if k!="QDRANT_API_KEY" else f"{k} prefix = {(os.getenv(k) or '')[:8]}…")
for k in ["QDRANT_URL","QDRANT_API_KEY","QDRANT_COLLECTION","QDRANT_VECTOR_SIZE","ENABLE_WEB_SEARCH","WEB_MODEL"]:
    show(k)
