import logging
import os
from uuid import uuid4
from hashlib import sha256

import chromadb

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# RENDER FIX: Use PERSIST_DIR env var if set (point to Render Persistent Disk mount path)
# In Render dashboard -> Environment, set: PERSIST_DIR=/var/data
_DATA_ROOT = os.getenv("PERSIST_DIR", os.path.join(BASE_DIR, "..", "uploads"))
CHROMA_DIR = os.path.join(_DATA_ROOT, "chroma_db")
os.makedirs(CHROMA_DIR, exist_ok=True)

client = chromadb.PersistentClient(path=CHROMA_DIR)
_collection_cache = {}


def _safe_collection_name(user_id: str) -> str:
    digest = sha256(user_id.encode("utf-8")).hexdigest()[:16]
    return f"mindvault_{digest}"


def get_collection(user_id: str):
    collection_name = _safe_collection_name(user_id)
    if collection_name not in _collection_cache:
        try:
            _collection_cache[collection_name] = client.get_collection(collection_name)
        except Exception:
            _collection_cache[collection_name] = client.create_collection(name=collection_name)
    return _collection_cache[collection_name]


def store_chunks(chunks, page_num, user_id: str, source_id="unknown"):
    col = get_collection(user_id=user_id)
    logger.info("Storing %s chunks for page %s", len(chunks), page_num)

    success_count = 0
    for i, chunk in enumerate(chunks):
        try:
            chunk_id = f"{source_id}_p{page_num}_c{i}_{uuid4().hex[:8]}"
            col.add(
                documents=[chunk],
                ids=[chunk_id],
                metadatas=[
                    {
                        "source_id": source_id,
                        "page": int(page_num),
                        "chunk_index": int(i),
                    }
                ],
            )
            success_count += 1
        except Exception as e:
            logger.warning("Failed to add chunk for page %s index %s: %s", page_num, i, str(e)[:200])
            continue

    logger.info("Successfully stored %s/%s chunks", success_count, len(chunks))
    return success_count


def delete_user_collection(user_id: str) -> None:
    collection_name = _safe_collection_name(user_id)
    _collection_cache.pop(collection_name, None)
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass