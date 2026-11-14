from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from fastapi.concurrency import run_in_threadpool
from app.core.dependencies import get_retrieval_service

from app.api.chat import router as chat_router
from app.api.llm import router as llm_router
from app.api.policies import router as policies_router
from app.api.users import router as users_router
import time

from fastapi import Request

@asynccontextmanager
async def lifespan(app: FastAPI):
    started = time.perf_counter()

    await run_in_threadpool(get_retrieval_service)

    print(
        f"RAG MODELS READY: "
        f"{time.perf_counter() - started:.3f}s"
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

    print(
        f"\nFULL HTTP REQUEST: "
        f"{request.method} {request.url.path} "
        f"{total:.3f} sec\n"
    )

    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(chat_router)
app.include_router(users_router)
app.include_router(policies_router)
app.include_router(llm_router)


@app.get("/health")
async def health():
    return {"status": "ok"}