"""Exceptions whose text is shown to the user."""


class CgError(Exception):
    """An operation failed; the message fits the status area."""


class LoginRequired(CgError):
    """The server lists need the CyberGhost account login."""


class LoginRejected(CgError):
    """The account login was refused although a password was sent."""


class AuthRejected(CgError):
    """The VPN server answered AUTH_FAILED."""
