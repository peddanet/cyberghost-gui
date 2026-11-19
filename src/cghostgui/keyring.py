"""Passwords in the desktop key ring through ``secret-tool``."""
from cghostgui import proc


class Keyring:
    """Stores one secret per kind; failures never stop the application."""

    _ATTRIBUTES = ["application", "cyberghost-gui", "kind"]

    @classmethod
    def get(cls, kind: str) -> str | None:
        """Read a secret.

        Args:
            kind: ``openvpn`` or ``account``.

        Returns:
            The secret, or None if there is none.
        """
        result = proc.run(["secret-tool", "lookup", *cls._ATTRIBUTES, kind], 10)
        return result.out.rstrip("\n") if result.code == 0 and result.out else None

    @classmethod
    def put(cls, kind: str, secret: str) -> bool:
        """Store a secret.

        Args:
            kind: ``openvpn`` or ``account``.
            secret: Value; passed on standard input, never as an argument.

        Returns:
            True if the key ring accepted it.
        """
        command = ["secret-tool", "store", "--label", f"CyberGhost GUI ({kind})",
                   *cls._ATTRIBUTES, kind]
        return proc.run(command, 10, stdin=secret).code == 0

    @classmethod
    def clear(cls, kind: str) -> None:
        """Remove a secret.

        Args:
            kind: ``openvpn`` or ``account``.
        """
        proc.run(["secret-tool", "clear", *cls._ATTRIBUTES, kind], 10)
