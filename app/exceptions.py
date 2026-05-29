class AppError(Exception):
    status_code = 500

    def __init__(self, message="Errore interno del server"):
        self.message = message
        super().__init__(message)


class ValidationError(AppError):
    status_code = 400


class ForbiddenError(AppError):
    status_code = 403


class NotFoundError(AppError):
    status_code = 404


class ConflictError(AppError):
    status_code = 409
