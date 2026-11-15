"""Authenticated app-only SSH PTY transport."""
import asyncio
import codecs
import fcntl
import os
import pty
import signal
import struct
import termios

import anyio
from fastapi import WebSocket, WebSocketDisconnect

MONITOR_SCRIPT = "export TERM=xterm-256color; if command -v btop >/dev/null 2>&1; then exec btop; elif command -v htop >/dev/null 2>&1; then exec htop; else exec top; fi"


async def read_pty(fd):
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    def ready():
        if future.done():
            return
        try:
            future.set_result(os.read(fd, 16384))
        except BlockingIOError:
            return
        except OSError:
            future.set_result(b"")
    loop.add_reader(fd, ready)
    try:
        return await future
    finally:
        loop.remove_reader(fd)


async def write_pty(fd, data):
    loop = asyncio.get_running_loop()
    while data:
        try:
            count = os.write(fd, data)
            data = data[count:]
        except BlockingIOError:
            ready = loop.create_future()
            def writable():
                if not ready.done():
                    ready.set_result(None)
            loop.add_writer(fd, writable)
            try:
                await ready
            finally:
                loop.remove_writer(fd)


def resize(fd, cols, rows):
    if isinstance(cols, bool) or isinstance(rows, bool) or not isinstance(cols, int) or not isinstance(rows, int) or not (1 <= cols <= 500 and 1 <= rows <= 300):
        raise ValueError("invalid terminal dimensions")
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))


async def terminal(websocket: WebSocket, gateway, host_id, mode, slots):
    try:
        host = gateway.resolve(host_id)
        if mode not in ("monitor", "shell"):
            raise ValueError("unsupported terminal mode")
    except ValueError:
        await websocket.close(code=1008)
        return
    # A session never queues indefinitely holding an accepted socket.
    if slots.locked():
        await websocket.close(code=1013)
        return
    await slots.acquire()
    master = slave = None
    process = None
    tasks = []
    try:
        await websocket.accept()
        master, slave = pty.openpty()
        os.set_blocking(master, False)
        resize(master, 100, 30)
        args = gateway.ssh.argv(host, tty=True)
        if mode == "monitor":
            import shlex
            args += ["sh -lc " + shlex.quote(MONITOR_SCRIPT)]
        process = await asyncio.create_subprocess_exec(*args, stdin=slave, stdout=slave, stderr=slave, start_new_session=True, env={**os.environ, "TERM": "xterm-256color"})
        os.close(slave)
        slave = None
        async def output():
            decoder = codecs.getincrementaldecoder("utf-8")("replace")
            while data := await read_pty(master):
                text = decoder.decode(data)
                if text:
                    await websocket.send_json({"type": "output", "data": text})
            tail = decoder.decode(b"", final=True)
            if tail:
                await websocket.send_json({"type": "output", "data": tail})
            await process.wait()
            await websocket.send_json({"type": "exit", "status": process.returncode})
        async def receive():
            while True:
                message = await websocket.receive_json()
                if not isinstance(message, dict):
                    raise ValueError("invalid terminal message")
                if message.get("type") == "input":
                    data = message.get("data")
                    if not isinstance(data, str) or len(data.encode()) > 32768:
                        raise ValueError("terminal input exceeds limit")
                    await write_pty(master, data.encode())
                elif message.get("type") == "resize":
                    resize(master, message.get("cols"), message.get("rows"))
                    if process.returncode is None:
                        os.killpg(process.pid, signal.SIGWINCH)
                else:
                    raise ValueError("invalid terminal message")
        tasks = [asyncio.create_task(output()), asyncio.create_task(receive())]
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    except Exception:
        try:
            await websocket.send_json({"type": "error", "message": "Terminal session unavailable or invalid message"})
        except Exception:
            pass
    finally:
        # ASGI servers may cancel the request immediately on disconnect. Shield
        # cleanup so the SSH process is reaped even in a cancelled task scope.
        with anyio.CancelScope(shield=True):
            for task in tasks:
                if not task.done():
                    task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            if process and process.returncode is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                    await asyncio.wait_for(process.wait(), 2)
                except asyncio.TimeoutError:
                    os.killpg(process.pid, signal.SIGKILL)
                    await process.wait()
                except ProcessLookupError:
                    pass
            for fd in (master, slave):
                if fd is not None:
                    os.close(fd)
            slots.release()
            try:
                await websocket.close()
            except Exception:
                pass
