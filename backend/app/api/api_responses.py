from fastapi.responses import JSONResponse
from typing import Any, Optional, Dict, List
from pydantic import BaseModel
from app.utils.config import settings


class APIResponseModel(BaseModel):
    """标准API响应模型"""
    success: bool = True
    message: str = "Success"
    data: Optional[Any] = None


class APIErrorResponseModel(BaseModel):
    """标准API错误响应模型"""
    success: bool = False
    message: str
    error_code: Optional[str] = None
    details: Optional[Any] = None


# ==================== 2xx Success Responses ====================

def success_response(data: Any = None, message: str = "操作成功", cookie: Optional[str] = None, delete_cookie: Optional[bool] = False) -> JSONResponse:
    """
    200 OK - 请求成功
    用于: GET请求成功, PUT/PATCH更新成功
    """
    response_data = APIResponseModel(
        success=True,
        message=message,
        data=data
    ).model_dump()
    if cookie:
        res = JSONResponse(
            status_code=200,
            content=response_data
        )
        res.set_cookie(
            key="token",
            value=cookie,
            max_age=60 * 60 * 24,
            httponly=True,
            secure=settings.COOKIE_SECURE,
            samesite="lax",
            path="/"
        )
        return res
    if delete_cookie:
        res = JSONResponse(
            status_code=200,
            content=response_data
        )
        res.delete_cookie(
            key="token",
            path="/"
        )
        return res
    return JSONResponse(
        status_code=200,
        content=response_data
    )


def created_response(data: Any = None, message: str = "资源创建成功") -> JSONResponse:
    """
    201 Created - 资源创建成功
    用于: POST请求成功创建新资源
    """
    response_data = APIResponseModel(
        success=True,
        message=message,
        data=data
    ).model_dump()
    return JSONResponse(
        status_code=201,
        content=response_data
    )


def accepted_response(data: Any = None, message: str = "请求已接受") -> JSONResponse:
    """
    202 Accepted - 请求已接受，但处理未完成
    用于: 异步任务已提交
    """
    response_data = APIResponseModel(
        success=True,
        message=message,
        data=data
    ).model_dump()
    return JSONResponse(
        status_code=202,
        content=response_data
    )


def no_content_response() -> JSONResponse:
    """
    204 No Content - 请求成功但无返回内容
    用于: DELETE请求成功
    """
    return JSONResponse(
        status_code=204,
        content=None
    )


# ==================== 4xx Client Error Responses ====================

def bad_request_response(
    message: str = "请求参数错误",
    error_code: Optional[str] = "BAD_REQUEST",
    details: Any = None
) -> JSONResponse:
    """
    400 Bad Request - 客户端请求错误
    用于: 请求参数验证失败, 格式错误
    """
    response_data = APIErrorResponseModel(
        success=False,
        message=message,
        error_code=error_code,
        details=details
    ).model_dump(exclude_none=True)
    return JSONResponse(
        status_code=400,
        content=response_data
    )


def unauthorized_response(
    message: str = "未授权，请先登录",
    error_code: Optional[str] = "UNAUTHORIZED",
    details: Any = None
) -> JSONResponse:
    """
    401 Unauthorized - 未认证
    用于: 缺少认证信息或认证失败
    """
    response_data = APIErrorResponseModel(
        success=False,
        message=message,
        error_code=error_code,
        details=details
    ).model_dump(exclude_none=True)
    return JSONResponse(
        status_code=401,
        content=response_data,
        headers={"WWW-Authenticate": "Bearer"}
    )


def payment_required_response(
    message: str = "金币不足",
    error_code: Optional[str] = "PAYMENT_REQUIRED",
    details: Any = None
) -> JSONResponse:
    """
    402 Payment Required - 需要支付
    用于: 金币不足, 需要充值或消费不足
    """
    response_data = APIErrorResponseModel(
        success=False,
        message=message,
        error_code=error_code,
        details=details
    ).model_dump(exclude_none=True)
    return JSONResponse(
        status_code=402,
        content=response_data
    )


def forbidden_response(
    message: str = "禁止访问",
    error_code: Optional[str] = "FORBIDDEN",
    details: Any = None
) -> JSONResponse:
    """
    403 Forbidden - 已认证但无权限
    用于: 用户已登录但没有访问该资源的权限
    """
    response_data = APIErrorResponseModel(
        success=False,
        message=message,
        error_code=error_code,
        details=details
    ).model_dump(exclude_none=True)
    return JSONResponse(
        status_code=403,
        content=response_data
    )


def not_found_response(
    message: str = "资源不存在",
    error_code: Optional[str] = "NOT_FOUND",
    details: Any = None
) -> JSONResponse:
    """
    404 Not Found - 资源不存在
    用于: 请求的资源未找到
    """
    response_data = APIErrorResponseModel(
        success=False,
        message=message,
        error_code=error_code,
        details=details
    ).model_dump(exclude_none=True)
    return JSONResponse(
        status_code=404,
        content=response_data
    )


def method_not_allowed_response(
    message: str = "请求方法不允许",
    error_code: Optional[str] = "METHOD_NOT_ALLOWED",
    allowed_methods: Optional[List[str]] = None
) -> JSONResponse:
    """
    405 Method Not Allowed - 请求方法不允许
    用于: HTTP方法不支持
    """
    response_data = APIErrorResponseModel(
        success=False,
        message=message,
        error_code=error_code,
        details={"allowed_methods": allowed_methods} if allowed_methods else None
    ).model_dump(exclude_none=True)
    headers = {}
    if allowed_methods:
        headers["Allow"] = ", ".join(allowed_methods)
    return JSONResponse(
        status_code=405,
        content=response_data,
        headers=headers
    )


def conflict_response(
    message: str = "资源冲突",
    error_code: Optional[str] = "CONFLICT",
    details: Any = None
) -> JSONResponse:
    """
    409 Conflict - 资源冲突
    用于: 资源已存在, 状态冲突
    """
    response_data = APIErrorResponseModel(
        success=False,
        message=message,
        error_code=error_code,
        details=details
    ).model_dump(exclude_none=True)
    return JSONResponse(
        status_code=409,
        content=response_data
    )


def unprocessable_entity_response(
    message: str = "无法处理的实体",
    error_code: Optional[str] = "UNPROCESSABLE_ENTITY",
    details: Any = None
) -> JSONResponse:
    """
    422 Unprocessable Entity - 语义错误
    用于: 请求格式正确但语义错误, 业务逻辑验证失败
    """
    response_data = APIErrorResponseModel(
        success=False,
        message=message,
        error_code=error_code,
        details=details
    ).model_dump(exclude_none=True)
    return JSONResponse(
        status_code=422,
        content=response_data
    )


def too_many_requests_response(
    message: str = "请求过于频繁",
    error_code: Optional[str] = "TOO_MANY_REQUESTS",
    retry_after: Optional[int] = None
) -> JSONResponse:
    """
    429 Too Many Requests - 请求过于频繁
    用于: 超过速率限制
    """
    response_data = APIErrorResponseModel(
        success=False,
        message=message,
        error_code=error_code,
        details={"retry_after": retry_after} if retry_after else None
    ).model_dump(exclude_none=True)
    headers = {}
    if retry_after:
        headers["Retry-After"] = str(retry_after)
    return JSONResponse(
        status_code=429,
        content=response_data,
        headers=headers
    )


# ==================== 5xx Server Error Responses ====================

def internal_server_error_response(
    message: str = "服务器内部错误",
    error_code: Optional[str] = "INTERNAL_SERVER_ERROR",
    details: Any = None
) -> JSONResponse:
    """
    500 Internal Server Error - 服务器内部错误
    用于: 未预期的服务器错误
    """
    response_data = APIErrorResponseModel(
        success=False,
        message=message,
        error_code=error_code,
        details=details
    ).model_dump(exclude_none=True)
    return JSONResponse(
        status_code=500,
        content=response_data
    )


def service_unavailable_response(
    message: str = "服务暂时不可用",
    error_code: Optional[str] = "SERVICE_UNAVAILABLE",
    retry_after: Optional[int] = None
) -> JSONResponse:
    """
    503 Service Unavailable - 服务不可用
    用于: 服务器维护或过载
    """
    response_data = APIErrorResponseModel(
        success=False,
        message=message,
        error_code=error_code,
        details={"retry_after": retry_after} if retry_after else None
    ).model_dump(exclude_none=True)
    headers = {}
    if retry_after:
        headers["Retry-After"] = str(retry_after)
    return JSONResponse(
        status_code=503,
        content=response_data,
        headers=headers
    )


# ==================== Utility Functions ====================

def paginated_response(
    items: List[Any],
    total: int,
    page: int,
    page_size: int,
    message: str = "查询成功"
) -> JSONResponse:
    """
    分页响应
    用于: 返回分页数据
    """
    data = {
        "items": items,
        "pagination": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }
    }
    return success_response(data=data, message=message)


def validation_error_response(errors: Dict[str, Any]) -> JSONResponse:
    """
    验证错误响应
    用于: 表单验证失败
    """
    return bad_request_response(
        message="数据验证失败",
        error_code="VALIDATION_ERROR",
        details={"errors": errors}
    )
