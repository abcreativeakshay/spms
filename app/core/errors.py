"""Consistent API error shape: {code, message, details}."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    code = "internal_error"
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code
        self.details = details


class BadRequest(AppError):
    code = "bad_request"
    status_code = status.HTTP_400_BAD_REQUEST


class Unauthorized(AppError):
    code = "unauthorized"
    status_code = status.HTTP_401_UNAUTHORIZED

    def __init__(self, message: str = "Invalid or missing authentication token", **kw: Any) -> None:
        super().__init__(message, **kw)


class Forbidden(AppError):
    code = "forbidden"
    status_code = status.HTTP_403_FORBIDDEN


class NotFound(AppError):
    code = "not_found"
    status_code = status.HTTP_404_NOT_FOUND


class Conflict(AppError):
    code = "conflict"
    status_code = status.HTTP_409_CONFLICT


class Unprocessable(AppError):
    code = "unprocessable"
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY


class ServiceUnavailable(AppError):
    code = "service_unavailable"
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE


def _payload(code: str, message: str, details: Any = None) -> dict[str, Any]:
    body: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        body["details"] = details
    return body


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_payload(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_payload("validation_error", "Request validation failed", exc.errors()),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {401: "unauthorized", 403: "forbidden", 404: "not_found"}.get(
            exc.status_code, "http_error"
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_payload(code, str(exc.detail)),
        )
