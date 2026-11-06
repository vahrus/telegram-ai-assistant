"""Ошибки с текстом, который можно показать пользователю."""


class AppError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class DialogNotFoundError(AppError):
    pass


class LastDialogError(AppError):
    pass


class ValidationError(AppError):
    pass


class AIError(AppError):
    pass
