"""Generate an ADMIN_PASSWORD_HASH to paste into the deployment environment.

    python -m app.hashpw              # prompts, input hidden
    python -m app.hashpw 'my-secret'  # non-interactive (visible in shell history)

Set the printed value as ADMIN_PASSWORD_HASH; the plaintext never leaves your
machine.
"""
from __future__ import annotations

import getpass
import sys

from .passwords import hash_password


def main() -> None:
    plaintext = sys.argv[1] if len(sys.argv) > 1 else getpass.getpass("Admin password: ")
    if not plaintext:
        raise SystemExit("empty password")
    print(hash_password(plaintext))


if __name__ == "__main__":
    main()
