"""Tell a running application to switch to the installed release."""
import subprocess
import sys

from cghostgui import paths

GDBUS = ["gdbus", "call", "--session", "--dest", paths.APP_ID, "--object-path", paths.APP_PATH,
         "--method", "org.gtk.Actions.Activate", "reload", "[]", "{}"]


def main() -> int:
    """Send the request.

    Returns:
        0 if a running application accepted it, 1 if none runs.
    """
    done = subprocess.run(GDBUS, capture_output=True, text=True, timeout=5, check=False)
    return 0 if done.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
