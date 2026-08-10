"""Typed facade over the committed wire code generated from proto/body.proto."""

from collections.abc import Callable
from typing import cast

import grpc
from grpc import aio

from cortex_seam._generated.body_pb2 import (
    AckReminderReply,
    AckReminderRequest,
    Cancel,
    CaptureScreenReply,
    CaptureScreenRequest,
    CaptureTarget,
    ClientEvent,
    ConfirmRequest,
    ConfirmResolved,
    ConfirmResponse,
    DeleteSessionReply,
    DeleteSessionRequest,
    DueReminder,
    GetPreferencesReply,
    GetPreferencesRequest,
    GetSessionMessagesReply,
    GetSessionMessagesRequest,
    GetVolumeRequest,
    HealthReply,
    HealthRequest,
    ImageBlob,
    InjectInputReply,
    InjectInputRequest,
    KeyChord,
    ListDueRemindersReply,
    ListDueRemindersRequest,
    ListSessionsReply,
    ListSessionsRequest,
    NotifyReply,
    NotifyRequest,
    Preference,
    RenameSessionReply,
    RenameSessionRequest,
    SeamError,
    ServerEvent,
    SessionMessage,
    SessionSummary,
    SetPreferenceReply,
    SetPreferenceRequest,
    SetSessionPinnedReply,
    SetSessionPinnedRequest,
    SetVolumeRequest,
    StatusUpdate,
    TextDelta,
    ToolActivity,
    ToolOutcome,
    TurnComplete,
    TypeText,
    UserTurn,
    VolumeState,
)

# The generated gRPC module ships no .pyi, so the two registration helpers come back untyped
# and are re-annotated below.
from cortex_seam._generated.body_pb2_grpc import (  # pyright: ignore[reportMissingTypeStubs]
    BodyServiceServicer,
    BodyServiceStub,
    BrainServiceServicer,
    BrainServiceStub,
)
from cortex_seam._generated.body_pb2_grpc import (  # pyright: ignore[reportMissingTypeStubs]
    add_BodyServiceServicer_to_server as _untyped_add_body,  # pyright: ignore[reportUnknownVariableType]
)
from cortex_seam._generated.body_pb2_grpc import (  # pyright: ignore[reportMissingTypeStubs]
    add_BrainServiceServicer_to_server as _untyped_add_brain,  # pyright: ignore[reportUnknownVariableType]
)

type _AddBodyServicer = Callable[[BodyServiceServicer, grpc.Server | aio.Server], None]
type _AddBrainServicer = Callable[[BrainServiceServicer, grpc.Server | aio.Server], None]

# N816 is suppressed twice below: the gRPC code generator fixes these mixedCase names.
add_BodyServiceServicer_to_server = cast("_AddBodyServicer", _untyped_add_body)  # noqa: N816
add_BrainServiceServicer_to_server = cast("_AddBrainServicer", _untyped_add_brain)  # noqa: N816

# The metadata key the shared token travels under, in both directions. The body declares its own
# Rust constant of the same value twice, and `scripts/crosscheck.py` fails if the three differ.
SEAM_TOKEN_HEADER = "x-cortex-seam-token"  # noqa: S105 - the header NAME, not a secret

__all__ = [
    "SEAM_TOKEN_HEADER",
    "AckReminderReply",
    "AckReminderRequest",
    "BodyServiceServicer",
    "BodyServiceStub",
    "BrainServiceServicer",
    "BrainServiceStub",
    "Cancel",
    "CaptureScreenReply",
    "CaptureScreenRequest",
    "CaptureTarget",
    "ClientEvent",
    "ConfirmRequest",
    "ConfirmResolved",
    "ConfirmResponse",
    "DeleteSessionReply",
    "DeleteSessionRequest",
    "DueReminder",
    "GetPreferencesReply",
    "GetPreferencesRequest",
    "GetSessionMessagesReply",
    "GetSessionMessagesRequest",
    "GetVolumeRequest",
    "HealthReply",
    "HealthRequest",
    "ImageBlob",
    "InjectInputReply",
    "InjectInputRequest",
    "KeyChord",
    "ListDueRemindersReply",
    "ListDueRemindersRequest",
    "ListSessionsReply",
    "ListSessionsRequest",
    "NotifyReply",
    "NotifyRequest",
    "Preference",
    "RenameSessionReply",
    "RenameSessionRequest",
    "SeamError",
    "ServerEvent",
    "SessionMessage",
    "SessionSummary",
    "SetPreferenceReply",
    "SetPreferenceRequest",
    "SetSessionPinnedReply",
    "SetSessionPinnedRequest",
    "SetVolumeRequest",
    "StatusUpdate",
    "TextDelta",
    "ToolActivity",
    "ToolOutcome",
    "TurnComplete",
    "TypeText",
    "UserTurn",
    "VolumeState",
    "add_BodyServiceServicer_to_server",
    "add_BrainServiceServicer_to_server",
]
