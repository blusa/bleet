"""Local administrative CLI. Secret outputs are never emitted by serve."""
import argparse
import getpass
import json
import os
import sys

from .config import Config, SCOPES
from .state import State


def secret_output(value, output):
    text = value + "\n"
    if output:
        # Exclusive creation prevents accidental overwrite or following a symlink.
        fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(text)
    else:
        # stdout only is intentional: callers can use `umask 077; ... > code.txt`.
        print(value)


def main():
    parser = argparse.ArgumentParser(prog="bleetd")
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("serve", "enroll", "token", "revoke"):
        sub = commands.add_parser(command)
        sub.add_argument("--config", required=True)
        if command == "serve":
            sub.add_argument("--host", default="127.0.0.1")
            sub.add_argument("--port", type=int, default=8791)
        elif command in ("enroll", "token"):
            sub.add_argument("--device-scopes", default=",".join(sorted(SCOPES)))
            sub.add_argument("--output", help="Sensitive output file: created exclusively with mode 0600")
            if command == "enroll":
                sub.add_argument("--ttl", type=int, default=600)
            else:
                sub.add_argument("--name", required=True)
    args = parser.parse_args()
    config = Config.load(args.config)
    if args.command == "serve":
        import uvicorn
        from .app import create_app
        uvicorn.run(create_app(config), host=args.host, port=args.port, access_log=False, log_level="warning", ws_max_size=65536, server_header=False)
        return
    state = State(config.state_dir / "state.db")
    if args.command == "revoke":
        state.revoke_token(getpass.getpass("Token to revoke (hidden): "))
        return
    scopes = [scope.strip() for scope in args.device_scopes.split(",")]
    if args.output and os.path.lexists(args.output):
        parser.error("output file already exists")
    value = state.issue_enrollment(scopes, args.ttl) if args.command == "enroll" else state.issue_token(args.name, scopes)
    secret_output(value, args.output)


if __name__ == "__main__":
    main()
