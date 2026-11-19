"""Exceptions whose text is shown to the user."""


class CgError(Exception):
    """An operation failed; the message fits the status area."""


class LoginRequired(CgError):
    """The server lists need the CyberGhost account login."""


class AuthRejected(CgError):
    """The VPN server answered AUTH_FAILED."""
