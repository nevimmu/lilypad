'''Configuration: TOML at ~/.config/lilypad/config.toml (created on first run).'''

from __future__ import annotations

import logging
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

DEFAULT_CLASSES = [
	'kitty',
	'foot',
	'Alacritty',
	'org.wezfurlong.wezterm',
	'com.mitchellh.ghostty',
]

DEFAULT_TOML = '''\
# lilypad configuration. Restart lilypad after editing.

# Fraction of the monitor's usable area (minus bars) the floating window
# takes, per axis. The window is centered in that area.
scale = 0.71

# Window classes to manage (case-insensitive, exact match).
# Find a window's class with: hyprctl clients | grep class
classes = [
    "kitty",
    "foot",
    "Alacritty",
    "org.wezfurlong.wezterm",
    "com.mitchellh.ghostty",
]
'''


@dataclass
class Config:
	scale: float = 0.71
	classes: list[str] = field(default_factory=lambda: list(DEFAULT_CLASSES))

	def matches(self, window_class: str) -> bool:
		wanted = {c.lower() for c in self.classes}
		return window_class.lower() in wanted


def default_path() -> Path:
	base = os.environ.get('XDG_CONFIG_HOME') or str(Path.home() / '.config')
	return Path(base) / 'lilypad' / 'config.toml'


def load(path: Path | None = None) -> Config:
	'''Load config, writing the default file if missing. Never raises.'''
	path = path or default_path()
	if not path.exists():
		try:
			path.parent.mkdir(parents=True, exist_ok=True)
			path.write_text(DEFAULT_TOML)
			log.info('wrote default config to %s', path)
		except OSError as e:
			log.warning('could not write default config %s: %s', path, e)
		return Config()
	try:
		data = tomllib.loads(path.read_text())
		scale = float(data.get('scale', 0.71))
		if not 0.05 <= scale <= 1.0:
			raise ValueError(f'scale must be between 0.05 and 1.0, got {scale}')
		classes = data.get('classes', DEFAULT_CLASSES)
		if not isinstance(classes, list) or not all(isinstance(c, str) for c in classes):
			raise ValueError('classes must be a list of strings')
		return Config(scale=scale, classes=list(classes))
	except (OSError, ValueError, tomllib.TOMLDecodeError) as e:
		log.error('invalid config %s (%s); using defaults', path, e)
		return Config()
