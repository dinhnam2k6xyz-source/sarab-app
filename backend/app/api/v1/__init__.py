from fastapi import APIRouter
from app.api.v1.analyze import router as analyze_router
from app.api.v1.novels import router as novels_router
from app.api.v1.chapters import router as chapters_router
from app.api.v1.translate import router as translate_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.glossary import router as glossary_router
from app.api.v1.proxy import router as proxy_router

api_router = APIRouter()

api_router.include_router(analyze_router, tags=["Analyze"])
api_router.include_router(novels_router, prefix="/novels", tags=["Novels"])
api_router.include_router(chapters_router, tags=["Chapters & Reader"])
api_router.include_router(translate_router, prefix="/translate", tags=["Translation"])
api_router.include_router(jobs_router, tags=["Jobs & Realtime"])
api_router.include_router(glossary_router, tags=["Glossary"])
api_router.include_router(proxy_router, tags=["Proxy"])
