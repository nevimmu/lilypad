'''Pure decision logic: given Hyprland state, decide which windows to float/tile.

No I/O here so it can be unit-tested with plain dicts shaped like
`hyprctl clients -j` / `hyprctl monitors -j`.
'''

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .config import Config


@dataclass(frozen=True)
class Float:
	address: str
	x: int
	y: int
	w: int
	h: int


@dataclass(frozen=True)
class Tile:
	address: str
	# Tiled window already in the workspace. Re-tiling inserts our window as the
	# "new" one, so the daemon swaps the two to honor dwindle force_split.
	swap_with: str | None = None


Action = Float | Tile


@dataclass
class State:
	# address -> monitor id it was last placed on (windows WE floated)
	managed: dict[str, int] = field(default_factory=dict)
	# addresses the user manually tiled; left alone until another tiled window
	# shows up in their workspace (or they close)
	manual: set[str] = field(default_factory=set)


def usable_box(mon: dict) -> tuple[float, float, float, float]:
	'''Return (x, y, w, h) of the monitor's usable area in logical pixels.'''
	w, h = mon['width'], mon['height']
	if mon.get('transform', 0) % 2 == 1:  # 90/270 degree rotations
		w, h = h, w
	scale = mon.get('scale', 1) or 1
	w, h = w / scale, h / scale
	left, top, right, bottom = mon.get('reserved', [0, 0, 0, 0])
	return (
		mon['x'] + left,
		mon['y'] + top,
		w - left - right,
		h - top - bottom,
	)


def geometry(mon: dict, ratio: float) -> tuple[int, int, int, int]:
	ux, uy, uw, uh = usable_box(mon)
	w, h = round(uw * ratio), round(uh * ratio)
	x = round(ux + (uw - w) / 2)
	y = round(uy + (uh - h) / 2)
	return x, y, w, h


def reconcile(
	clients: list[dict], monitors: list[dict], state: State, cfg: Config
) -> list[Action]:
	'''Compute actions and update `state` to reflect them.'''
	mons = {m['id']: m for m in monitors}
	live = [c for c in clients if c.get('mapped', True) and not c.get('hidden', False)]
	by_addr = {c['address']: c for c in live}

	# Forget windows that disappeared.
	for addr in list(state.managed):
		if addr not in by_addr:
			del state.managed[addr]
	state.manual &= by_addr.keys()

	# A managed window that is no longer floating was toggled by the user.
	for addr in list(state.managed):
		if not by_addr[addr]['floating']:
			del state.managed[addr]
			state.manual.add(addr)

	# Special workspaces (scratchpads) have no "id" key, only a name, so key on that.
	by_ws: dict[str, list[dict]] = defaultdict(list)
	for c in live:
		ws = c['workspace']
		by_ws[str(ws.get('name') or ws.get('id'))].append(c)

	actions: list[Action] = []
	for wins in by_ws.values():
		tiled = [c for c in wins if not c['floating']]
		managed_here = [c for c in wins if c['address'] in state.managed]

		# Manual overrides expire once another tiled window shares the workspace.
		for c in wins:
			if c['address'] in state.manual and any(
				t['address'] != c['address'] for t in tiled
			):
				state.manual.discard(c['address'])

		for c in managed_here:
			addr = c['address']
			# another tiled window, or another window we floated -> back to tiling
			if tiled or len(managed_here) > 1:
				del state.managed[addr]
				other = tiled[0]['address'] if len(tiled) == 1 and len(managed_here) == 1 else None
				actions.append(Tile(addr, swap_with=other))
			elif state.managed[addr] != c['monitor'] and c['monitor'] in mons:
				# moved to another monitor: recenter there
				state.managed[addr] = c['monitor']
				actions.append(Float(addr, *geometry(mons[c['monitor']], cfg.scale)))

		if len(tiled) == 1 and not managed_here:
			c = tiled[0]
			addr = c['address']
			if (
				cfg.matches(c.get('class', ''))
				and addr not in state.manual
				and not c.get('fullscreen', 0)
				and not c.get('pinned', False)
				and c['monitor'] in mons
			):
				state.managed[addr] = c['monitor']
				actions.append(Float(addr, *geometry(mons[c['monitor']], cfg.scale)))

	return actions
