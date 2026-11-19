"""Run external programs with argument lists, never through a shell."""
import shutil
import subprocess
from typing import Mapping, NamedTuple


class Result(NamedTuple):
    """Outcome of an external program."""

    code: int
    out: str
    err: str


def run(cmd: list[str], timeout: int = 60, env: Mapping[str, str] | None = None,
        stdin: str | None = None) -> Result:
    """Run a program and capture its output.

    Args:
        cmd: Program and arguments.
        timeout: Limit in seconds.
        env: Environment, or None to inherit it.
        stdin: Text for standard input, or None for no input.

    Returns:
        Exit code and output; 124 after a timeout, 127 if the program is missing.
    """
    program = shutil.which(cmd[0])
    if program is None:
        return Result(127, "", f"Programm fehlt: {cmd[0]}")
    try:
        done = subprocess.run([program, *cmd[1:]], capture_output=True, text=True,
                              timeout=timeout, env=env, input=stdin, check=False,
                              stdin=None if stdin is not None else subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return Result(124, "", f"Zeitüberschreitung: {cmd[0]}")
    return Result(done.returncode, done.stdout, done.stderr)
