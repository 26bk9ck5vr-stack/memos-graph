"""Unified error handling for API endpoints."""

from functools import wraps
from typing import Callable, TypeVar, Any
from fastapi import HTTPException
from fastapi.responses import JSONResponse
import logging
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError

logger = logging.getLogger(__name__)

# Type variable for async functions
AsyncFunc = TypeVar("AsyncFunc", bound=Callable[..., Any])


class APIError(Exception):
    """Base API error."""

    def __init__(self, message: str, code: str = "api_error", status_code: int = 500):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(self.message)


class NotFoundError(APIError):
    """Resource not found error."""

    def __init__(self, message: str = "Resource not found"):
        super().__init__(message=message, code="not_found", status_code=404)


class ValidationError(APIError):
    """Validation error."""

    def __init__(self, message: str = "Validation failed"):
        super().__init__(message=message, code="validation_error", status_code=400)


class ConflictError(APIError):
    """Resource conflict error."""

    def __init__(self, message: str = "Resource already exists"):
        super().__init__(message=message, code="conflict", status_code=409)


class DatabaseError(APIError):
    """Database error."""

    def __init__(self, message: str = "Database operation failed"):
        super().__init__(message=message, code="database_error", status_code=500)


def handle_api_errors(func: AsyncFunc) -> AsyncFunc:
    """
    Decorator to handle common API errors uniformly.

    Catches:
    - SQLAlchemyError → 500
    - HTTPException → pass through (already formatted)
    - APIError subclasses → respective status codes
    - Exception → 500

    Usage:
        @router.get("/items")
        @handle_api_errors
        async def get_items(session: AsyncSession = Depends(get_session)):
            ...
    """

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await func(*args, **kwargs)
        except HTTPException:
            # Re-raise FastAPI HTTP exceptions as-is
            raise
        except APIError:
            # Re-raise our custom API errors (will be handled by exception handlers)
            raise
        except IntegrityError as e:
            logger.exception(f"Integrity error in {func.__name__}: {e}")
            raise ConflictError(f"Database integrity violation: {str(e.orig) if hasattr(e, 'orig') else str(e)}")
        except OperationalError as e:
            logger.exception(f"Database operational error in {func.__name__}: {e}")
            raise DatabaseError(f"Database connection error: {str(e)}")
        except SQLAlchemyError as e:
            logger.exception(f"SQLAlchemy error in {func.__name__}: {e}")
            raise DatabaseError(f"Database error: {str(e)}")
        except Exception as e:
            logger.exception(f"Unexpected error in {func.__name__}: {e}")
            raise APIError(message=str(e), code="internal_error", status_code=500)

    return wrapper  # type: ignore


def create_error_response(error: APIError) -> JSONResponse:
    """Create a standardized error response."""
    return JSONResponse(
        status_code=error.status_code,
        content={"error": {"code": error.code, "message": error.message}},
    )


def register_exception_handlers(app):
    """
    Register exception handlers on a FastAPI app.

    Usage in server.py:
        from memos_graph.api.errors import register_exception_handlers
        register_exception_handlers(app)
    """
    from fastapi import Request
    from fastapi.responses import JSONResponse

    @app.exception_handler(APIError)
    async def api_error_handler(request: Request, exc: APIError):
        return create_error_response(exc)

    @app.exception_handler(DatabaseError)
    async def database_error_handler(request: Request, exc: DatabaseError):
        logger.exception(f"Database error: {exc}")
        return create_error_response(exc)

    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError):
        return create_error_response(exc)

    @app.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError):
        return create_error_response(exc)

    @app.exception_handler(ConflictError)
    async def conflict_error_handler(request: Request, exc: ConflictError):
        return create_error_response(exc)
