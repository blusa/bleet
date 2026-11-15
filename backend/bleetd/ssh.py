"""Checked-host-key SSH with bounded output and subprocess cleanup."""
import asyncio
import os
import signal
import tempfile
from pathlib import Path


async def bounded_process(argv, timeout=15, limit=2_000_000, input_data=None):
    process = await asyncio.create_subprocess_exec(*argv, stdin=asyncio.subprocess.PIPE if input_data is not None else asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, start_new_session=True)
    async def read(stream):
        output = bytearray()
        while chunk := await stream.read(65536):
            output.extend(chunk)
            if len(output) > limit:
                raise ValueError("command output exceeds limit")
        return bytes(output)
    async def communicate():
        if input_data is not None:
            process.stdin.write(input_data)
            await process.stdin.drain()
            process.stdin.close()
        stdout, _ = await asyncio.gather(read(process.stdout), read(process.stderr))
        status = await process.wait()
        if status:
            # Remote stderr can contain credentials; never forward it to clients/logs.
            raise ValueError("remote command failed")
        return stdout.decode("utf-8", "replace")
    try:
        return await asyncio.wait_for(communicate(), timeout)
    finally:
        if process.returncode is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await process.wait()


class SSH:
    def __init__(self, config):
        self.config = config
        # A process-owned Unix socket must not survive container/process replacement.
        # /tmp also keeps OpenSSH's Unix socket path below its length limit on macOS.
        self._control_directory = tempfile.TemporaryDirectory(prefix="bleetd-ssh-", dir="/tmp")
        self.control_dir = Path(self._control_directory.name)

    def argv(self, host, tty=False):
        config = self.config
        args = ["ssh", "-F", config.ssh_config or "/dev/null", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", "-o", f"UserKnownHostsFile={config.known_hosts}", "-o", "GlobalKnownHostsFile=/dev/null", "-o", "ConnectTimeout=8", "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=2", "-o", "LogLevel=ERROR", "-o", "ControlMaster=auto", "-o", "ControlPersist=60", "-o", f"ControlPath={self.control_dir}/%C", "-p", str(host.port)]
        if config.identity_file:
            args += ["-i", config.identity_file, "-o", "IdentitiesOnly=yes"]
        args += ["-tt" if tty else "-T", "--", host.ssh_target]
        return args

    async def run(self, host, command, timeout=None):
        return await bounded_process(self.argv(host) + [command], timeout=timeout or self.config.collection_timeout)

    async def close(self):
        async def stop_master(host):
            args = self.argv(host)
            args[args.index("--"):args.index("--")] = ["-O", "exit"]
            try:
                await bounded_process(args, timeout=2, limit=4096)
            except Exception:
                pass  # No active master is normal for disabled/unreachable hosts.
        try:
            await asyncio.gather(*(stop_master(host) for host in self.config.hosts))
        finally:
            self._control_directory.cleanup()
