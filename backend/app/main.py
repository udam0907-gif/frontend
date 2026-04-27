from __future__ import annotations

import contextlib
from collections.abc import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging, get_logger
from app.database import init_db

logger = get_logger(__name__)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging()
    settings.ensure_storage_dirs()
    logger.info("startup", app_env=settings.app_env, model=settings.llm_model)
    await init_db()
    yield
    logger.info("shutdown")


app = FastAPI(
    title=settings.app_name,
    description="정부 R&D 과제 비용 집행 및 RCMS 매뉴얼 기반 Q&A 시스템",
    version="1.0.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def app_exception_handler(request: Request, exc: AppError) -> JSONResponse:
    logger.warning("app_exception", path=str(request.url), error=exc.message, code=exc.error_code)
    return JSONResponse(status_code=exc.status_code, content={"error": exc.error_code, "message": exc.message, "details": exc.details})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled_exception", path=str(request.url), error=str(exc), exc_info=True)
    return JSONResponse(status_code=500, content={"error": "INTERNAL_SERVER_ERROR", "message": "서버 내부 오류가 발생했습니다."})


# Register routers
from app.api.v1 import company_settings, projects, templates, expenses, documents, validation, export, rcms, legal as legal_router, vendors, vendor_pool  # noqa: E402

prefix = settings.api_v1_prefix
app.include_router(projects.router, prefix=prefix + "/projects", tags=["프로젝트"])
app.include_router(templates.router, prefix=prefix + "/templates", tags=["템플릿"])
app.include_router(expenses.router, prefix=prefix + "/expenses", tags=["비용 항목"])
app.include_router(documents.router, prefix=prefix + "/documents", tags=["문서"])
app.include_router(validation.router, prefix=prefix + "/validation", tags=["유효성 검사"])
app.include_router(export.router, prefix=prefix + "/export", tags=["내보내기"])
app.include_router(company_settings.router, prefix=prefix + "/company-settings", tags=["회사 설정"])
app.include_router(rcms.router, prefix=prefix + "/rcms", tags=["RCMS Q&A"])
app.include_router(legal_router.router, prefix=prefix + "/rcms", tags=["법령 자료"])
app.include_router(vendors.router, prefix=prefix + "/vendors", tags=["업체"])
app.include_router(vendor_pool.router, prefix=prefix + "/vendor-pool", tags=["업체 템플릿 풀"])


@app.get("/health", tags=["헬스체크"])
async def health() -> dict:
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env}
