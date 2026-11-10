"""One-at-a-time ownership for Krita's shared Layers Docker edit state."""

from __future__ import annotations


class SelectionSessionUnavailableError(RuntimeError):
    """Raised when another node already owns the Krita Layers Docker edit session."""


_active_picker: object | None = None


def claim_selection_session(picker: object) -> None:
    """Claim the single shared edit session for either Krita node picker."""
    global _active_picker

    if _active_picker is picker:
        return
    if _active_picker is not None:
        message = "Another Krita node is already editing the Layers Docker"
        raise SelectionSessionUnavailableError(message)

    _active_picker = picker


def release_selection_session(picker: object) -> None:
    """Release the shared edit session only when called by its current owner."""
    global _active_picker

    if _active_picker is picker:
        _active_picker = None
