from fastapi import APIRouter

from app.api.routes import accounts, auth, billing, content_calendar, dashboard, pages, posts, publish_logs, settings, users

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(accounts.router, prefix="/accounts", tags=["accounts"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(content_calendar.router, prefix="/content-calendar", tags=["content-calendar"])
api_router.include_router(posts.router, prefix="/posts", tags=["posts"])
api_router.include_router(publish_logs.router, prefix="/publish-logs", tags=["publish-logs"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
api_router.include_router(pages.router, prefix="/pages", tags=["pages"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(billing.router, prefix="/billing", tags=["billing"])
