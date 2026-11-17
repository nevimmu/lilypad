'''Minimal Hyprland IPC client (request socket + event socket).'''

from __future__ import annotations

import json
import os
import socket
from collections.abc import Iterator
from pathlib import Path


class IPCError(RuntimeError):
	pass


def _socket_dir() -> Path:
	sig = os.environ.get('HYPRLAND_INSTANCE_SIGNATURE')
	runtime = os.environ.get('XDG_RUNTIME_DIR')
	if not sig or not runtime:
		raise IPCError(
			'HYPRLAND_INSTANCE_SIGNATURE / XDG_RUNTIME_DIR not set; '
			'run lilypad from inside a Hyprland session'
		)
	return Path(runtime) / 'hypr' / sig


def request(cmd: str) -> str:
	s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
	try:
		s.connect(str(_socket_dir() / '.socket.sock'))
		s.sendall(cmd.encode())
		chunks = []
		while True:
			data = s.recv(65536)
			if not data:
				break
			chunks.append(data)
	except OSError as e:
		raise IPCError(f'IPC request failed: {e}') from e
	finally:
		s.close()
	return b''.join(chunks).decode()


def request_json(cmd: str):
	return json.loads(request(f'j/{cmd}'))


def clients() -> list[dict]:
	return request_json('clients')


def monitors() -> list[dict]:
	return request_json('monitors')


def get_int_option(name: str, default: int = 0) -> int:
	try:
		return int(request_json(f'getoption {name}').get('int', default))
	except (IPCError, ValueError, AttributeError):
		return default


def dispatch_batch(cmds: list[str]) -> str:
	'''Send several Lua dispatcher calls (e.g. \"hl.dsp.window.float({...})\") in one request.'''
	if not cmds:
		return ''
	batch = '[[BATCH]]' + ';'.join(f'dispatch {c}' for c in cmds)
	return request(batch)


def events() -> Iterator[tuple[str, str]]:
	'''Yield (event, data) from .socket2.sock. Ends when the socket closes.'''
	s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
	try:
		s.connect(str(_socket_dir() / '.socket2.sock'))
	except OSError as e:
		raise IPCError(f'cannot connect to event socket: {e}') from e
	buf = b''
	try:
		while True:
			data = s.recv(65536)
			if not data:
				return
			buf += data
			while b'\n' in buf:
				line, buf = buf.split(b'\n', 1)
				text = line.decode(errors='replace')
				name, _, payload = text.partition('>>')
				yield name, payload
	finally:
		s.close()
