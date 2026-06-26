# 레이어: Infrastructure — 도메인 공통 예외 (HTTP 무관)


class SoundBridgeException(Exception):
    """SoundBridge 도메인 기본 예외"""


# [MVP]
class TrackNotFoundException(SoundBridgeException):
    def __init__(self, track_id: str) -> None:
        self.track_id = track_id
        super().__init__(f"Track not found: {track_id}")


class OllamaApiException(SoundBridgeException):
    pass


class EmbeddingException(SoundBridgeException):
    pass


# [v1.1]
class UserNotFoundException(SoundBridgeException):
    pass


class UserAlreadyExistsException(SoundBridgeException):
    def __init__(self, email: str) -> None:
        self.email = email
        super().__init__(f"User already exists: {email}")


class InvalidCredentialsException(SoundBridgeException):
    pass


class EmailNotVerifiedException(SoundBridgeException):
    pass


class TokenExpiredException(SoundBridgeException):
    pass


class TokenInvalidException(SoundBridgeException):
    pass


class SavedTrackNotFoundException(SoundBridgeException):
    pass


class EmailSendException(SoundBridgeException):
    pass
