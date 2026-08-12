"""Assets validation and report download routes."""

from app.api.routes.validation_router import build_validation_router
from app.validation.assets.service import AssetsValidationService

SESSION_COOKIE = "datalens_assets_session"

router = build_validation_router(
    domain="assets",
    service_factory=AssetsValidationService,
    session_cookie=SESSION_COOKIE,
)
