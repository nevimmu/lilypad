'''Event loop: listen to Hyprland events, reconcile, dispatch.'''

from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Callable

from . import ipc
from .config import Config
from .logic import Action, Float, State, Tile, reconcile

log = logging.getLogger(__name__)

# Events after which the window/workspace picture may have changed.
RELEVANT = {
	'openwindow',
	'closewindow',
	'movewindow',
	'movewindowv2',
	'changefloatingmode',
	'fullscreen',
	'workspace',
	'workspacev2',
	'moveworkspace',
	'moveworkspacev2',
	'monitoradded',
	'monitorremoved',
	'monitoraddedv2',
	'monitorremovedv2',
	'windowtitle',  # some terminals set class late; harmless extra reconcile
}
DEBOUNCE = 0.04  # seconds


def to_commands(action: Action, force_split: int = 0) -> list[str]:
	'''Lua dispatcher calls (Hyprland >= 0.55 uses the Lua config API).'''
	win = f"window = 'address:{action.address}'"
	if isinstance(action, Float):
		return [
			f"hl.dsp.window.float({{ action = 'enable', {win} }})",
			f'hl.dsp.window.resize({{ x = {action.w}, y = {action.h}, exact = true, {win} }})',
			f'hl.dsp.window.move({{ x = {action.x}, y = {action.y}, exact = true, {win} }})',
		]
	cmds = [f"hl.dsp.window.float({{ action = 'disable', {win} }})"]
	if action.swap_with and force_split != 0:
		# dwindle:force_split 1/2 pins where *new* windows go; the other window
		# is the new one here, so it must take that slot instead of ours.
		cmds.append(
			f"hl.dsp.window.swap({{ target = 'address:{action.swap_with}', {win} }})"
		)
	return cmds


class Daemon:
	def __init__(
		self,
		cfg: Config,
		get_clients: Callable[[], list[dict]] = ipc.clients,
		get_monitors: Callable[[], list[dict]] = ipc.monitors,
		dispatch: Callable[[list[str]], object] = ipc.dispatch_batch,
		get_force_split: Callable[[], int] = lambda: ipc.get_int_option('dwindle:force_split'),
	) -> None:
		self._get_force_split = get_force_split
		self.cfg = cfg
		self.state = State()
		self._get_clients = get_clients
		self._get_monitors = get_monitors
		self._dispatch = dispatch

	def run_once(self) -> list[Action]:
		try:
			actions = reconcile(
				self._get_clients(), self._get_monitors(), self.state, self.cfg
			)
		except (ipc.IPCError, ValueError, KeyError) as e:
			log.warning('reconcile failed: %s', e)
			return []
		for act in actions:
			log.info('%s', act)
			try:
				fs = self._get_force_split() if isinstance(act, Tile) and act.swap_with else 0
				resp = self._dispatch(to_commands(act, fs))
				if isinstance(resp, str) and 'error' in resp.lower():
					log.warning('dispatch error: %s', resp)
			except ipc.IPCError as e:
				log.warning('dispatch failed: %s', e)
		return actions

	def run(self) -> None:
		'''Block until the event socket closes (Hyprland exit).'''
		self.run_once()
		q: queue.Queue[str | None] = queue.Queue()

		def reader() -> None:
			try:
				for name, _ in ipc.events():
					if name in RELEVANT:
						q.put(name)
			except ipc.IPCError as e:
				log.error('%s', e)
			finally:
				q.put(None)

		threading.Thread(target=reader, daemon=True).start()
		while True:
			ev = q.get()
			if ev is None:
				log.error('event socket closed; exiting')
				return
			# debounce: swallow the burst that follows
			closed = False
			while True:
				try:
					nxt = q.get(timeout=DEBOUNCE)
				except queue.Empty:
					break
				if nxt is None:
					closed = True
					break
			log.debug('event %s -> reconcile', ev)
			self.run_once()
			if closed:
				log.error('event socket closed; exiting')
				return
