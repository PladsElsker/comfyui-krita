"""One-at-a-time ownership for Krita's shared Layers Docker edit state."""

from __future__ import annotations


class SelectionSessionUnavailableError(RuntimeError):
    """Raised when another node already owns the Krita Layers Docker edit session."""


class _SelectionSession:
    """Hold the active picker without rebinding module-level state."""

    active_picker: object | None = None


_session = _SelectionSession()


def claim_selection_session(picker: object) -> None:
    """Claim the shared edit session, cancelling its previous owner first."""
    active_picker = _session.active_picker
    if active_picker is picker:
        return

    if active_picker is not None:
        if getattr(active_picker, "is_editing", False):
            cancel = getattr(active_picker, "cancel", None)
            if not callable(cancel):
                message = "The active Krita edit session cannot be cancelled"
                raise SelectionSessionUnavailableError(message)
            cancel()
        else:
            release_selection_session(active_picker)

        if _session.active_picker is not None:
            message = "The previous Krita edit session did not release ownership"
            raise SelectionSessionUnavailableError(message)

    _session.active_picker = picker


def release_selection_session(picker: object) -> None:
    """Release the shared edit session only when called by its current owner."""
    if _session.active_picker is picker:
        _session.active_picker = None
