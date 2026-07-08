from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ClientEvent(_message.Message):
    __slots__ = ("session_id", "user_turn", "cancel", "confirm_response")
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    USER_TURN_FIELD_NUMBER: _ClassVar[int]
    CANCEL_FIELD_NUMBER: _ClassVar[int]
    CONFIRM_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    user_turn: UserTurn
    cancel: Cancel
    confirm_response: ConfirmResponse
    def __init__(self, session_id: _Optional[str] = ..., user_turn: _Optional[_Union[UserTurn, _Mapping]] = ..., cancel: _Optional[_Union[Cancel, _Mapping]] = ..., confirm_response: _Optional[_Union[ConfirmResponse, _Mapping]] = ...) -> None: ...

class UserTurn(_message.Message):
    __slots__ = ("text", "images")
    TEXT_FIELD_NUMBER: _ClassVar[int]
    IMAGES_FIELD_NUMBER: _ClassVar[int]
    text: str
    images: _containers.RepeatedCompositeFieldContainer[ImageBlob]
    def __init__(self, text: _Optional[str] = ..., images: _Optional[_Iterable[_Union[ImageBlob, _Mapping]]] = ...) -> None: ...

class Cancel(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ServerEvent(_message.Message):
    __slots__ = ("text_delta", "tool_activity", "status", "turn_complete", "error", "confirm_request")
    TEXT_DELTA_FIELD_NUMBER: _ClassVar[int]
    TOOL_ACTIVITY_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    TURN_COMPLETE_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    CONFIRM_REQUEST_FIELD_NUMBER: _ClassVar[int]
    text_delta: TextDelta
    tool_activity: ToolActivity
    status: StatusUpdate
    turn_complete: TurnComplete
    error: SeamError
    confirm_request: ConfirmRequest
    def __init__(self, text_delta: _Optional[_Union[TextDelta, _Mapping]] = ..., tool_activity: _Optional[_Union[ToolActivity, _Mapping]] = ..., status: _Optional[_Union[StatusUpdate, _Mapping]] = ..., turn_complete: _Optional[_Union[TurnComplete, _Mapping]] = ..., error: _Optional[_Union[SeamError, _Mapping]] = ..., confirm_request: _Optional[_Union[ConfirmRequest, _Mapping]] = ...) -> None: ...

class TextDelta(_message.Message):
    __slots__ = ("text",)
    TEXT_FIELD_NUMBER: _ClassVar[int]
    text: str
    def __init__(self, text: _Optional[str] = ...) -> None: ...

class ToolActivity(_message.Message):
    __slots__ = ("tool_name", "summary")
    TOOL_NAME_FIELD_NUMBER: _ClassVar[int]
    SUMMARY_FIELD_NUMBER: _ClassVar[int]
    tool_name: str
    summary: str
    def __init__(self, tool_name: _Optional[str] = ..., summary: _Optional[str] = ...) -> None: ...

class StatusUpdate(_message.Message):
    __slots__ = ("state", "detail")
    STATE_FIELD_NUMBER: _ClassVar[int]
    DETAIL_FIELD_NUMBER: _ClassVar[int]
    state: str
    detail: str
    def __init__(self, state: _Optional[str] = ..., detail: _Optional[str] = ...) -> None: ...

class TurnComplete(_message.Message):
    __slots__ = ("turn_id",)
    TURN_ID_FIELD_NUMBER: _ClassVar[int]
    turn_id: str
    def __init__(self, turn_id: _Optional[str] = ...) -> None: ...

class SeamError(_message.Message):
    __slots__ = ("code", "message")
    CODE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    code: str
    message: str
    def __init__(self, code: _Optional[str] = ..., message: _Optional[str] = ...) -> None: ...

class ConfirmRequest(_message.Message):
    __slots__ = ("confirm_id", "tool_name", "arguments_json", "reason")
    CONFIRM_ID_FIELD_NUMBER: _ClassVar[int]
    TOOL_NAME_FIELD_NUMBER: _ClassVar[int]
    ARGUMENTS_JSON_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    confirm_id: str
    tool_name: str
    arguments_json: str
    reason: str
    def __init__(self, confirm_id: _Optional[str] = ..., tool_name: _Optional[str] = ..., arguments_json: _Optional[str] = ..., reason: _Optional[str] = ...) -> None: ...

class ConfirmResponse(_message.Message):
    __slots__ = ("confirm_id", "approved")
    CONFIRM_ID_FIELD_NUMBER: _ClassVar[int]
    APPROVED_FIELD_NUMBER: _ClassVar[int]
    confirm_id: str
    approved: bool
    def __init__(self, confirm_id: _Optional[str] = ..., approved: _Optional[bool] = ...) -> None: ...

class HealthRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class HealthReply(_message.Message):
    __slots__ = ("ready", "detail")
    READY_FIELD_NUMBER: _ClassVar[int]
    DETAIL_FIELD_NUMBER: _ClassVar[int]
    ready: bool
    detail: str
    def __init__(self, ready: _Optional[bool] = ..., detail: _Optional[str] = ...) -> None: ...

class ListSessionsRequest(_message.Message):
    __slots__ = ("limit",)
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    limit: int
    def __init__(self, limit: _Optional[int] = ...) -> None: ...

class ListSessionsReply(_message.Message):
    __slots__ = ("sessions",)
    SESSIONS_FIELD_NUMBER: _ClassVar[int]
    sessions: _containers.RepeatedCompositeFieldContainer[SessionSummary]
    def __init__(self, sessions: _Optional[_Iterable[_Union[SessionSummary, _Mapping]]] = ...) -> None: ...

class SessionSummary(_message.Message):
    __slots__ = ("session_id", "title", "preview", "last_activity_unix_ms")
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    PREVIEW_FIELD_NUMBER: _ClassVar[int]
    LAST_ACTIVITY_UNIX_MS_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    title: str
    preview: str
    last_activity_unix_ms: int
    def __init__(self, session_id: _Optional[str] = ..., title: _Optional[str] = ..., preview: _Optional[str] = ..., last_activity_unix_ms: _Optional[int] = ...) -> None: ...

class GetSessionMessagesRequest(_message.Message):
    __slots__ = ("session_id",)
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    def __init__(self, session_id: _Optional[str] = ...) -> None: ...

class GetSessionMessagesReply(_message.Message):
    __slots__ = ("messages",)
    MESSAGES_FIELD_NUMBER: _ClassVar[int]
    messages: _containers.RepeatedCompositeFieldContainer[SessionMessage]
    def __init__(self, messages: _Optional[_Iterable[_Union[SessionMessage, _Mapping]]] = ...) -> None: ...

class SessionMessage(_message.Message):
    __slots__ = ("role", "text", "turn_id", "at_unix_ms")
    ROLE_FIELD_NUMBER: _ClassVar[int]
    TEXT_FIELD_NUMBER: _ClassVar[int]
    TURN_ID_FIELD_NUMBER: _ClassVar[int]
    AT_UNIX_MS_FIELD_NUMBER: _ClassVar[int]
    role: str
    text: str
    turn_id: str
    at_unix_ms: int
    def __init__(self, role: _Optional[str] = ..., text: _Optional[str] = ..., turn_id: _Optional[str] = ..., at_unix_ms: _Optional[int] = ...) -> None: ...

class ListDueRemindersRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ListDueRemindersReply(_message.Message):
    __slots__ = ("reminders",)
    REMINDERS_FIELD_NUMBER: _ClassVar[int]
    reminders: _containers.RepeatedCompositeFieldContainer[DueReminder]
    def __init__(self, reminders: _Optional[_Iterable[_Union[DueReminder, _Mapping]]] = ...) -> None: ...

class DueReminder(_message.Message):
    __slots__ = ("reminder_id", "text", "fired_at_unix_ms", "recurring", "tainted", "session_id")
    REMINDER_ID_FIELD_NUMBER: _ClassVar[int]
    TEXT_FIELD_NUMBER: _ClassVar[int]
    FIRED_AT_UNIX_MS_FIELD_NUMBER: _ClassVar[int]
    RECURRING_FIELD_NUMBER: _ClassVar[int]
    TAINTED_FIELD_NUMBER: _ClassVar[int]
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    reminder_id: str
    text: str
    fired_at_unix_ms: int
    recurring: bool
    tainted: bool
    session_id: str
    def __init__(self, reminder_id: _Optional[str] = ..., text: _Optional[str] = ..., fired_at_unix_ms: _Optional[int] = ..., recurring: _Optional[bool] = ..., tainted: _Optional[bool] = ..., session_id: _Optional[str] = ...) -> None: ...

class AckReminderRequest(_message.Message):
    __slots__ = ("reminder_id",)
    REMINDER_ID_FIELD_NUMBER: _ClassVar[int]
    reminder_id: str
    def __init__(self, reminder_id: _Optional[str] = ...) -> None: ...

class AckReminderReply(_message.Message):
    __slots__ = ("acked",)
    ACKED_FIELD_NUMBER: _ClassVar[int]
    acked: bool
    def __init__(self, acked: _Optional[bool] = ...) -> None: ...

class CaptureScreenRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class CaptureScreenReply(_message.Message):
    __slots__ = ("image",)
    IMAGE_FIELD_NUMBER: _ClassVar[int]
    image: ImageBlob
    def __init__(self, image: _Optional[_Union[ImageBlob, _Mapping]] = ...) -> None: ...

class ImageBlob(_message.Message):
    __slots__ = ("data", "mime_type", "width", "height")
    DATA_FIELD_NUMBER: _ClassVar[int]
    MIME_TYPE_FIELD_NUMBER: _ClassVar[int]
    WIDTH_FIELD_NUMBER: _ClassVar[int]
    HEIGHT_FIELD_NUMBER: _ClassVar[int]
    data: bytes
    mime_type: str
    width: int
    height: int
    def __init__(self, data: _Optional[bytes] = ..., mime_type: _Optional[str] = ..., width: _Optional[int] = ..., height: _Optional[int] = ...) -> None: ...

class GetVolumeRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SetVolumeRequest(_message.Message):
    __slots__ = ("level", "mute")
    LEVEL_FIELD_NUMBER: _ClassVar[int]
    MUTE_FIELD_NUMBER: _ClassVar[int]
    level: float
    mute: bool
    def __init__(self, level: _Optional[float] = ..., mute: _Optional[bool] = ...) -> None: ...

class VolumeState(_message.Message):
    __slots__ = ("level", "muted")
    LEVEL_FIELD_NUMBER: _ClassVar[int]
    MUTED_FIELD_NUMBER: _ClassVar[int]
    level: float
    muted: bool
    def __init__(self, level: _Optional[float] = ..., muted: _Optional[bool] = ...) -> None: ...

class InjectInputRequest(_message.Message):
    __slots__ = ("type_text", "key_chord")
    TYPE_TEXT_FIELD_NUMBER: _ClassVar[int]
    KEY_CHORD_FIELD_NUMBER: _ClassVar[int]
    type_text: TypeText
    key_chord: KeyChord
    def __init__(self, type_text: _Optional[_Union[TypeText, _Mapping]] = ..., key_chord: _Optional[_Union[KeyChord, _Mapping]] = ...) -> None: ...

class TypeText(_message.Message):
    __slots__ = ("text",)
    TEXT_FIELD_NUMBER: _ClassVar[int]
    text: str
    def __init__(self, text: _Optional[str] = ...) -> None: ...

class KeyChord(_message.Message):
    __slots__ = ("keys",)
    KEYS_FIELD_NUMBER: _ClassVar[int]
    keys: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, keys: _Optional[_Iterable[str]] = ...) -> None: ...

class InjectInputReply(_message.Message):
    __slots__ = ("applied",)
    APPLIED_FIELD_NUMBER: _ClassVar[int]
    applied: bool
    def __init__(self, applied: _Optional[bool] = ...) -> None: ...

class NotifyRequest(_message.Message):
    __slots__ = ("title", "body", "reminder_id", "tainted")
    TITLE_FIELD_NUMBER: _ClassVar[int]
    BODY_FIELD_NUMBER: _ClassVar[int]
    REMINDER_ID_FIELD_NUMBER: _ClassVar[int]
    TAINTED_FIELD_NUMBER: _ClassVar[int]
    title: str
    body: str
    reminder_id: str
    tainted: bool
    def __init__(self, title: _Optional[str] = ..., body: _Optional[str] = ..., reminder_id: _Optional[str] = ..., tainted: _Optional[bool] = ...) -> None: ...

class NotifyReply(_message.Message):
    __slots__ = ("shown",)
    SHOWN_FIELD_NUMBER: _ClassVar[int]
    shown: bool
    def __init__(self, shown: _Optional[bool] = ...) -> None: ...
