"""Replacement of the operating system for the tests."""
import shlex
from types import SimpleNamespace
from typing import Any

from prettytable_stub import table

from cghostgui import paths
from cghostgui.proc import Result

CITIES = {"de": {"frankfurt": [("frankfurt-s01-i01", 40), ("frankfurt-s01-i02", 12)],
                 "berlin": [("berlin-s02-i07", 5)]},
          "us": {"new york": [("newyork-s23-i12", 30)], "atlanta": [("atlanta-s01-i01", 20)]}}
SERVICES = [("Video One", "US"), ("Video Two", "DE")]
ACCOUNT_PASSWORD = "acc$pw"
VPN_PASSWORD = "vpn secret"


class FakeProcess:
    """Stands in for the running ``nmcli connection up``."""

    def __init__(self, system: "FakeSystem", cmd: list[str]) -> None:
        """Start the fake.

        Args:
            system: Fake system.
            cmd: Command line.
        """
        self.system = system
        self.returncode: int | None = None
        self.output = ""
        self.password = ""
        with open(cmd[cmd.index("passwd-file") + 1], encoding="utf-8") as handle:
            self.password = handle.read().split(":", 1)[1].strip()

    def __enter__(self) -> "FakeProcess":
        """Enter the context.

        Returns:
            This object.
        """
        return self

    def __exit__(self, *_: Any) -> None:
        """Leave the context."""

    def poll(self) -> int | None:
        """Advance the fake connection.

        Returns:
            Exit code or None while running.
        """
        mode = self.system.connect_mode
        if mode == "hang":
            return self.returncode
        if self.password != VPN_PASSWORD or mode == "reject":
            self.system.journal += "AUTH: Received control message: AUTH_FAILED\n"
            return self.returncode
        if mode == "fail":
            self.returncode, self.output = 4, "Warning: x\nError: Timeout expired (40 seconds)\n"
        elif mode == "broken":
            self.returncode, self.output = 4, "Error: something else\n"
        elif mode == "silent":
            self.returncode, self.output = 4, ""
        else:
            self.returncode, self.output = 0, "ok\n"
            self.system.state = "activated"
        return self.returncode

    def terminate(self) -> None:
        """End the fake."""
        self.returncode = -15

    def communicate(self, timeout: int = 0) -> tuple[str, None]:
        """Return the output.

        Args:
            timeout: Ignored.

        Returns:
            Output pair.
        """
        del timeout
        return self.output, None


class FakeSystem:  # pylint: disable=too-many-instance-attributes
    """Answers every external program the application calls."""

    def __init__(self) -> None:
        """Start with a known profile and no connection."""
        self.calls: list[list[str]] = []
        self.state = ""
        self.remote = "87-1-ch.cg-dialup.net"
        self.profile = True
        self.username = "vpnuser"
        self.fail_nmcli = ""
        self.journal = ""
        self.cursor = "c1"
        self.connect_mode = "ok"
        self.keyring: dict[str, str] = {}
        self.keyring_works = True
        self.public: dict[str, str] | None = {"ip": "203.0.113.5", "country": "DE",
                                              "city": "Berlin", "org": "Example"}
        self.ipv6_seen = ""
        self.ipv6_route = Result(2, "", "unreachable")
        self.ping_ok = True
        self.vendor_output: str | None = None
        self.ages = "65\n"

    def popen(self, cmd: list[str], **_: Any) -> FakeProcess:
        """Replace ``subprocess.Popen`` for the connection.

        Args:
            cmd: Command line.
            **_: Ignored options.

        Returns:
            Fake process.
        """
        self.calls.append(cmd)
        return FakeProcess(self, cmd)

    def namespace(self) -> SimpleNamespace:
        """Build the replacement of the ``subprocess`` module.

        Returns:
            Namespace.
        """
        return SimpleNamespace(Popen=self.popen, DEVNULL=-3, PIPE=-1, STDOUT=-2)

    def _nmcli(self, args: list[str]) -> Result:
        """Answer nmcli.

        Args:
            args: Arguments.

        Returns:
            Result.
        """
        if self.fail_nmcli and self.fail_nmcli in " ".join(args):
            return Result(1, "", "Error: refused\n")
        query = self._nmcli_query(args)
        if query is not None:
            return query
        if args[:2] == ["connection", "down"]:
            self.state = ""
        elif args[:2] == ["connection", "import"]:
            self.profile = True
            return Result(0, "Connection 'openvpn' (11111111-2222-3333-4444-555555555555) "
                             "successfully added.\n", "")
        elif args[:2] == ["connection", "modify"]:
            for word in args:
                if word.startswith("remote="):
                    self.remote = word[7:]
                elif word.startswith("username="):
                    self.username = word[9:]
        return Result(0, "", "")

    def _nmcli_query(self, args: list[str]) -> Result | None:
        """Answer the read-only forms of nmcli.

        Args:
            args: Arguments.

        Returns:
            Result, or None for other forms.
        """
        answers = {
            "NAME": Result(0, "lan\nCyberGhost-GUI\n" if self.profile else "lan\n", ""),
            "GENERAL.STATE": Result(0 if self.state else 10, f"{self.state}\n", ""),
            "GENERAL.IP-IFACE": Result(0, "lo\n" if self.state == "activated" else "\n", ""),
            "vpn.data": Result(0, f"cipher = x, remote = {self.remote}, port = 443\n", ""),
        }
        if args[:3] == ["-t", "-f", "NAME"]:
            return answers["NAME"]
        return answers.get(args[1]) if args[0] == "-g" else None

    def _secret(self, cmd: list[str], stdin: str | None) -> Result:
        """Answer secret-tool.

        Args:
            cmd: Command line.
            stdin: Input.

        Returns:
            Result.
        """
        kind = cmd[-1]
        if cmd[1] == "lookup":
            value = self.keyring.get(kind)
            return Result(0, value, "") if value else Result(1, "", "")
        if cmd[1] == "clear":
            self.keyring.pop(kind, None)
            return Result(0, "", "")
        if not self.keyring_works:
            return Result(1, "", "locked")
        self.keyring[kind] = stdin or ""
        return Result(0, "", "")

    def _vendor(self, args: list[str]) -> Result:
        """Answer the official program.

        Args:
            args: Arguments.

        Returns:
            Result with a table.
        """
        if self.vendor_output is not None:
            return Result(1, self.vendor_output, "")
        home = paths.vendor_home()
        config = (home / "config.ini").read_text(encoding="utf-8")
        if not (home / "token").exists():
            if f"password = {ACCOUNT_PASSWORD.replace('$', '$$')}" not in config:
                return Result(1, "Authentication error! Wrong login credentials\n", "")
            (home / "token").write_text("jwt", encoding="utf-8")
        options: dict[str, str | None] = {}
        key = ""
        for word in args:
            if word.startswith("--"):
                key = word[2:]
                options[key] = None
            else:
                options[key] = word.lower()
        return Result(0, self._vendor_table(options), "")

    @staticmethod
    def _vendor_table(options: dict[str, str | None]) -> str:
        """Print the table the options ask for.

        Args:
            options: Parsed arguments.

        Returns:
            Table.
        """
        code, city = options.get("country-code"), options.get("city")
        if "streaming" in options and options["streaming"] is None:
            return table(["No.", "Service", "Country Code"],
                         [[i + 1, *row] for i, row in enumerate(SERVICES)])
        if code is None:
            return table(["No.", "Country Name", "Country Code"],
                         [[1, "Germany", "DE"], [2, "United States", "US"]])
        rows: list[list[Any]] = []
        for name, servers in sorted(CITIES.get(code, {}).items()):
            if city and name == city:
                rows += [[len(rows) + 1, name.title(), s, f"{u}%"] for s, u in servers]
            elif not city:
                mean = sum(u for _, u in servers) // len(servers)
                rows.append([len(rows) + 1, name.title(), len(servers), f"{mean}%"])
        return table(["No.", "City", "Instance", "Usage"], rows)

    def _curl(self, cmd: list[str]) -> Result:
        """Answer curl.

        Args:
            cmd: Command line.

        Returns:
            Result.
        """
        if "-6" in cmd:
            return Result(0, self.ipv6_seen, "") if self.ipv6_seen else Result(7, "", "")
        if self.public is None:
            return Result(7, "", "no route")
        pairs = ", ".join(f'"{k}": "{v}"' for k, v in self.public.items())
        return Result(0, "{" + pairs + "}", "")

    def run(self, cmd: list[str], timeout: int = 60, env: Any = None,
            stdin: str | None = None) -> Result:
        """Replace ``proc.run``.

        Args:
            cmd: Command line.
            timeout: Ignored.
            env: Ignored.
            stdin: Input.

        Returns:
            Result.

        Raises:
            AssertionError: The program is not expected.
        """
        del timeout, env
        self.calls.append(cmd)
        name = cmd[0]
        answers = {
            "nmcli": lambda: self._nmcli(cmd[1:]),
            "secret-tool": lambda: self._secret(cmd, stdin),
            "curl": lambda: self._curl(cmd),
            "ip": lambda: self.ipv6_route,
            "ping": lambda: Result(0 if self.ping_ok else 1, "", ""),
            "ps": lambda: Result(0, self.ages, ""),
            "journalctl": lambda: self._journal(cmd),
        }
        if name in answers:
            return answers[name]()
        if name == str(paths.vendor_binary()):
            return self._vendor(cmd[1:])
        raise AssertionError("unexpected program: " + shlex.join(cmd))

    def _journal(self, cmd: list[str]) -> Result:
        """Answer journalctl.

        Args:
            cmd: Command line.

        Returns:
            Result.
        """
        if "--show-cursor" in cmd:
            self.journal = ""
            return Result(0, f"old line\n-- cursor: {self.cursor}\n", "")
        return Result(0, self.journal, "")
