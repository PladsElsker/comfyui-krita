"""One-at-a-time ownership for Krita's shared Layers Docker edit state."""

from __future__ import annotations


class SelectionSessionUnavailableError(RuntimeError):
    """Raised when another node already owns the Krita Layers Docker edit session."""


class _SelectionSession:
    """Hold the active picker without rebinding module-level state."""

    active_picker: object | None = None


_session = _SelectionSession()


def claim_selection_session(picker: object) -> None:
    """Claim the single shared edit session for either Krita node picker."""
    if _session.active_picker is picker:
        return
    if _session.active_picker is not None:
        message = "Another Krita node is already editing the Layers Docker"
        raise SelectionSessionUnavailableError(message)

    _session.active_picker = picker


def release_selection_session(picker: object) -> None:
    """Release the shared edit session only when called by its current owner."""
    if _session.active_picker is picker:
        _session.active_picker = None
