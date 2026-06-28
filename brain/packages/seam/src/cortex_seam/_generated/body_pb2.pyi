from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ClientEvent(_message.Message):
    __slots__ = ("session_id", "user_turn", "cancel")
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    USER_TURN_FIELD_NUMBER: _ClassVar[int]
    CANCEL_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    user_turn: UserTurn
    cancel: Cancel
    def __init__(self, session_id: _Optional[str] = ..., user_turn: _Optional[_Union[UserTurn, _Mapping]] = ..., cancel: _Optional[_Union[Cancel, _Mapping]] = ...) -> None: ...

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
    __slots__ = ("text_delta", "tool_activity", "status", "turn_complete", "error")
    TEXT_DELTA_FIELD_NUMBER: _ClassVar[int]
    TOOL_ACTIVITY_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    TURN_COMPLETE_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    text_delta: TextDelta
    tool_activity: ToolActivity
    status: StatusUpdate
    turn_complete: TurnComplete
    error: SeamError
    def __init__(self, text_delta: _Optional[_Union[TextDelta, _Mapping]] = ..., tool_activity: _Optional[_Union[ToolActivity, _Mapping]] = ..., status: _Optional[_Union[StatusUpdate, _Mapping]] = ..., turn_complete: _Optional[_Union[TurnComplete, _Mapping]] = ..., error: _Optional[_Union[SeamError, _Mapping]] = ...) -> None: ...

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
