from datetime import datetime
import hashlib
import io
import logging
import os
import shutil
import tempfile
from pathlib import Path
from threading import Lock

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from google import genai

from backend.auth import auth_router, auth_service, get_current_user
from backend.embedding_engine import EmbeddingEngine
from backend.pdf_processor import extract_text_from_pdf, split_text
from backend.rag_pipeline import RAGPipeline
from backend.reranker import CrossEncoderReranker
from backend.search_index import SearchIndex
from backend.vector_store import delete_user_collection, get_collection, store_chunks


load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "").strip()
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
GENAI_MODEL = os.getenv("GENAI_MODEL", "gemini-2.5-flash")

if not GOOGLE_API_KEY:
    raise RuntimeError("Missing GOOGLE_API_KEY in .env")
if not JWT_SECRET_KEY:
    raise RuntimeError("Missing JWT_SECRET_KEY in .env")

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = (BASE_DIR / ".." / "frontend").resolve()
UPLOAD_DIR = (BASE_DIR / ".." / "uploads").resolve()
USER_INDEX_BASE_DIR = UPLOAD_DIR / "search_index_users"
USERS_DB_PATH = UPLOAD_DIR / "users.json"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
USER_INDEX_BASE_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="MindVault AI", version="1.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth setup
auth_service.configure(
    users_db_path=str(USERS_DB_PATH),
    jwt_secret_key=JWT_SECRET_KEY,
    jwt_algorithm=JWT_ALGORITHM,
    access_token_expire_minutes=ACCESS_TOKEN_EXPIRE_MINUTES,
)
app.include_router(auth_router)

# AI and retrieval setup
genai_client = genai.Client(api_key=GOOGLE_API_KEY)
embedding_engine = EmbeddingEngine()
reranker = CrossEncoderReranker()

_index_lock = Lock()
_search_indexes: dict[str, SearchIndex] = {}


def get_user_index(user_id: str) -> SearchIndex:
    key = auth_service.normalize_email(user_id)
    key_hash = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    with _index_lock:
        if key not in _search_indexes:
            idx = SearchIndex(index_dir=str(USER_INDEX_BASE_DIR / key_hash))
            try:
                idx.load()
            except Exception as exc:
                logger.warning("Index load failed for %s: %s", key, exc)
            _search_indexes[key] = idx
        return _search_indexes[key]


def _clear_user_data(user_id: str) -> None:
    """Wipe ChromaDB collection + disk search index for a user."""
    key = auth_service.normalize_email(user_id)
    key_hash = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    delete_user_collection(user_id)
    shutil.rmtree(USER_INDEX_BASE_DIR / key_hash, ignore_errors=True)
    with _index_lock:
        _search_indexes.pop(key, None)


@app.get("/", response_class=HTMLResponse)
def serve_frontend() -> str:
    try:
        return (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    except Exception as exc:
        return f"<h1>Frontend Error</h1><p>{exc}</p>"


@app.post("/clear")
def clear_collection(current_user: dict = Depends(get_current_user)):
    """Delete all stored chunks and search index for the current user."""
    try:
        _clear_user_data(current_user["email"])
        return {"status": "success", "message": "Collection cleared"}
    except Exception as exc:
        logger.error("Clear error: %s", exc)
        return {"status": "error", "message": str(exc)}


@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    """
    Accepts a PDF, processes it entirely in memory using a temp file,
    and never persists the original PDF to disk.
    """
    try:
        filename = Path(file.filename).name
        if not filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF uploads are supported")

        user_id = current_user["email"]
        uhash = hashlib.sha256(auth_service.normalize_email(user_id).encode("utf-8")).hexdigest()[:16]
        source_id = f"{uhash}_{Path(filename).stem}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        pdf_bytes = await file.read()

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(pdf_bytes)
                tmp.flush()
                tmp_path = tmp.name

            _clear_user_data(user_id)

            pages = extract_text_from_pdf(tmp_path)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)


        total_chunks = 0
        all_chunks: list[str] = []
        for page in pages:
            text = page["text"]
            if not text.strip():
                continue
            chunks = split_text(text)
            total_chunks += store_chunks(chunks, page["page"], user_id=user_id, source_id=source_id)
            all_chunks.extend(chunks)

        indexed_chunks = 0
        try:
            indexed_chunks = get_user_index(user_id).append_chunks(all_chunks, embedding_engine)
        except Exception as exc:
            logger.warning("Index append failed for %s: %s", user_id, exc)

        return {
            "status": "success",
            "filename": filename,
            "pages": len(pages),
            "chunks": total_chunks,
            "indexed_chunks": indexed_chunks,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Upload error: %s", exc)
        return {"status": "error", "message": str(exc)}


@app.get("/query")
def query_vectors(
    q: str = Query(..., min_length=1),
    top_k: int = Query(10, ge=1, le=50),
    final_k: int = Query(3, ge=1, le=10),
    current_user: dict = Depends(get_current_user),
):
    try:
        query = q.strip()
        if not query:
            raise HTTPException(status_code=400, detail="Query cannot be empty")

        user_id = current_user["email"]
        data = get_collection(user_id=user_id).get()
        chunk_texts = data.get("documents", [])
        if not chunk_texts:
            return {"query": query, "results_count": 0, "results": []}

        try:
            idx = get_user_index(user_id)
            idx.ensure_ready(chunk_texts, embedding_engine)
            pipeline = RAGPipeline(
                embedding_engine=embedding_engine,
                retriever=idx.get_retriever(),
                reranker=reranker,
            )
            ranked = pipeline.process_query_with_scores(query, retrieve_k=top_k, final_k=final_k)
        except Exception as exc:
            logger.warning("RAG retrieval failed, fallback search: %s", exc)
            terms = [t.lower() for t in query.split() if t.strip()]
            scored: list[tuple[str, float]] = []
            for chunk in chunk_texts:
                score = sum(1 for t in terms if t in chunk.lower())
                if score > 0:
                    scored.append((chunk, float(score)))
            scored.sort(key=lambda x: x[1], reverse=True)
            ranked = scored[:final_k]

        results = [
            {
                "id": f"rank_{i + 1}",
                "document": doc,
                "distance": float(score),
                "score": float(score),
            }
            for i, (doc, score) in enumerate(ranked)
        ]
        return {"query": query, "results_count": len(results), "results": results}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Query error: %s", exc)
        return {"error": str(exc)}


@app.get("/all-documents")
def get_all_documents(current_user: dict = Depends(get_current_user)):
    try:
        data = get_collection(user_id=current_user["email"]).get()
        docs = data.get("documents", [])
        return {"total_count": len(docs), "documents": docs, "ids": data.get("ids", [])}
    except Exception as exc:
        logger.error("All-documents error: %s", exc)
        return {"error": str(exc)}


@app.get("/info")
def collection_info(current_user: dict = Depends(get_current_user)):
    try:
        user_id = current_user["email"]
        col = get_collection(user_id=user_id)
        return {
            "collection_name": col.name,
            "total_vectors": col.count(),
            "search_index": get_user_index(user_id).stats(),
            "status": "ready",
            "user": user_id,
        }
    except Exception as exc:
        logger.error("Info error: %s", exc)
        return {"error": str(exc)}


@app.post("/summarize")
def summarize_results(data: dict, current_user: dict = Depends(get_current_user)):
    try:
        query = data.get("query", "")
        results = data.get("results", [])
        if not results:
            return {"summary": "No results to summarize. Please search first."}

        combined_text = "\n".join([f"- {r['document']}" for r in results if "document" in r])
        prompt = (
            "You are a helpful tutor. Give a clear, simple explanation from the provided text only. "
            "If something is missing, say 'Not mentioned in document'.\n\n"
            f"Query: {query}\n\n"
            f"Document content:\n{combined_text}"
        )

        response = genai_client.models.generate_content(model=GENAI_MODEL, contents=prompt)
        return {
            "query": query,
            "summary": response.text,
            "results_count": len(results),
            "user": current_user["email"],
        }
    except Exception as exc:
        logger.error("Summarize error: %s", exc)
        return {"error": str(exc), "summary": "Failed to generate summary. Please try again."}


@app.delete("/account")
def delete_account(current_user: dict = Depends(get_current_user)):
    user_id = current_user["email"]
    uhash = hashlib.sha256(auth_service.normalize_email(user_id).encode("utf-8")).hexdigest()[:16]

    if not auth_service.delete_user_by_email(user_id):
        raise HTTPException(status_code=404, detail="User not found")

    _clear_user_data(user_id)
    shutil.rmtree(USER_INDEX_BASE_DIR / uhash, ignore_errors=True)

    return {"status": "success", "message": "Account deleted successfully"}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "mindvault-backend",
        "users_db_exists": USERS_DB_PATH.exists(),
        "gemini_configured": bool(GOOGLE_API_KEY),
    }


@app.get("/{asset_name}")
def serve_frontend_assets(asset_name: str):
    allowed = {
        "index.html", "login.html", "signup.html", "navbar.html",
        "app.js", "auth.js", "style.css", "auth.css",
    }
    if asset_name not in allowed:
        raise HTTPException(status_code=404, detail="Not found")

    asset_path = FRONTEND_DIR / asset_name
    if not asset_path.exists():
        raise HTTPException(status_code=404, detail="Frontend asset missing")
    return FileResponse(str(asset_path))