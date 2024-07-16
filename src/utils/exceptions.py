# ExceptionType


class BaseException(Exception):
    exception_type: str
    code: str = None
    message: str = None

    def keys(self):
        return ['exception_type', 'code', 'message']

    def __getitem__(self, key):
        return getattr(self, key)


class BusinessException(BaseException):
    exception_type: str = "BUSINESS"


class ApplicationException(Exception):
    exception_type: str = "APPLICATION"


class InvalidWorkItem(BusinessException):
    code: str = "INVALID_WORK_ITEM"
    message: str = "Invalid work item"


class UnexpectedError(ApplicationException):
    code: str = "UNEXPECTED_ERROR"
    message: str = "Unexpected error"


class InvalidInput(BusinessException):
    code: str = "INVALID_INPUT"
    message: str = "Invalid input"
