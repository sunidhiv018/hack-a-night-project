from typing import Generic, TypeVar, Optional, Any, List
from pydantic import BaseModel

T = TypeVar("T")

class StandardResponse(BaseModel, Generic[T]):
    success: bool = True
    message: str = "Operation completed successfully"
    data: Optional[T] = None
    errors: Optional[List[Any]] = None
    meta: Optional[dict] = None

class ErrorResponse(BaseModel):
    success: bool = False
    message: str
    errors: Optional[List[Any]] = None
    code: Optional[str] = "BAD_REQUEST"
