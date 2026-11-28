import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.db.database import engine

logger = logging.getLogger(__name__)


def _initialize_backend(app: FastAPI) -> None:
    started = time.perf_counter()
    print("Backend initialization started.", flush=True)
    logger.info("Starting backend initialization.")

    try:
        print("Importing API routes.", flush=True)
        logger.info("Importing API routes.")
        print("Importing chat API route.", flush=True)
        from app.api.chat import router as chat_router
        print("Imported chat API route.", flush=True)
        print("Importing LLM API route.", flush=True)
        from app.api.llm import router as llm_router
        print("Imported LLM API route.", flush=True)
        print("Importing policies API route.", flush=True)
        from app.api.policies import router as policies_router
        print("Imported policies API route.", flush=True)
        print("Importing users API route.", flush=True)
        from app.api.users import router as users_router
        print("Imported users API route.", flush=True)

        app.include_router(chat_router)
        app.include_router(users_router)
        app.include_router(policies_router)
        app.include_router(llm_router)
        print("API routes imported and registered.", flush=True)

        print("Retrieval model initialization started.", flush=True)
        logger.info("Starting retrieval model initialization.")
        from app.core.dependencies import get_retrieval_service

        get_retrieval_service()
        print("Retrieval model initialization finished.", flush=True)
    except Exception as exc:
        app.state.initialization_error = type(exc).__name__
        print(f"Backend initialization failed: {type(exc).__name__}.", flush=True)
        logger.exception("Backend initialization failed.")
        return

    app.state.backend_ready = True
    app.state.initialization_error = None
    elapsed = time.perf_counter() - started
    print(f"Backend ready after {elapsed:.3f}s.", flush=True)
    logger.info("Backend ready: %.3fs", elapsed)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.backend_ready = False
    app.state.initialization_error = None

    # Keep the ASGI lifespan in startup until routes and retrieval models are
    # initialized. Cloud Run's startup probe must not mark the revision ready
    # while backend initialization is still running in a detached thread.
    await run_in_threadpool(_initialize_backend, app)
    if app.state.initialization_error:
        raise RuntimeError(
            "Backend initialization failed "
            f"({app.state.initialization_error})."
        )

    yield


app = FastAPI(lifespan=lifespan)


@app.middleware("http")
async def request_timing_middleware(
    request: Request,
    call_next,
):
    start = time.perf_counter()
    request.state.http_started = start

    response = await call_next(request)
    total = time.perf_counter() - start

    # Route templates avoid logging policy/conversation IDs from URL paths.
    route = request.scope.get("route")
    logger.info(
        "HTTP %s %s completed in %.3f seconds.",
        request.method, getattr(route, "path", "unmatched"), total,
    )

    return response


@app.middleware("http")
async def require_backend_readiness(
    request: Request,
    call_next,
):
    if request.url.path not in {"/health", "/ready"} and not getattr(
        request.app.state, "backend_ready", False
    ):
        return JSONResponse(status_code=503, content={"detail": "Service is starting."})

    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://good-ai-advisor-e33k8mvkh-ubungmeisters-projects.vercel.app",
        "https://good-ai-advisor.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "alive"}


def _check_database_connection() -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1")).scalar_one()


@app.get("/ready")
async def readiness(request: Request):
    if not getattr(request.app.state, "backend_ready", False):
        error = getattr(request.app.state, "initialization_error", None)
        if error:
            raise HTTPException(status_code=503, detail="Backend initialization failed.")
        raise HTTPException(status_code=503, detail="Service is starting.")

    try:
        await run_in_threadpool(_check_database_connection)
    except Exception:
        logger.exception("Database readiness check failed.")
        raise HTTPException(status_code=503, detail="Database is unavailable.") from None

    return {"status": "ready", "database": "ok", "backend": "ready"}
