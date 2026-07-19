"""Typed facade over the committed wire code generated from proto/body.proto.

Pure re-exports, no logic: everything the rest of the brain needs from the seam is
imported from here, never from `cortex_seam._generated` directly.
"""

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
    TurnComplete,
    TypeText,
    UserTurn,
    VolumeState,
)

# The generated gRPC module ships no .pyi (wire code is gate-exempt, ADR-0002 d4).
# The classes re-export cleanly; the two untyped registration helpers are re-annotated
# below so consumers see full types. Narrow, justified ignores only, never a blanket Any.
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

# N816 suppressed twice below: the mixedCase names are fixed by the gRPC codegen interface.
add_BodyServiceServicer_to_server = cast("_AddBodyServicer", _untyped_add_body)  # noqa: N816
add_BrainServiceServicer_to_server = cast("_AddBrainServicer", _untyped_add_brain)  # noqa: N816

# The metadata key the seam token travels under, on either direction of the seam (ADR-0016;
# lowercase per gRPC). It lives here as a seam-contract detail both the brain's server-side
# interceptor and the brain's `BodyService` client (`cortex_body_client`, ADR-0023) share; the
# body's Rust side declares its own `const` of the same value.
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
    "TurnComplete",
    "TypeText",
    "UserTurn",
    "VolumeState",
    "add_BodyServiceServicer_to_server",
    "add_BrainServiceServicer_to_server",
]
