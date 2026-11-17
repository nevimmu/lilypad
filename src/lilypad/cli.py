from __future__ import annotations

import argparse
import logging
import signal
import sys
from pathlib import Path

from . import __version__, config, ipc
from .daemon import Daemon


def main(argv: list[str] | None = None) -> int:
	p = argparse.ArgumentParser(
		prog='lilypad',
		description='Float + center a lone terminal in a Hyprland workspace.',
	)
	p.add_argument('--config', type=Path, help='config file (default: ~/.config/lilypad/config.toml)')
	p.add_argument('-v', '--verbose', action='store_true', help='debug logging')
	p.add_argument('--version', action='version', version=__version__)
	args = p.parse_args(argv)

	logging.basicConfig(
		level=logging.DEBUG if args.verbose else logging.INFO,
		format='%(asctime)s %(levelname)s %(message)s',
	)
	cfg = config.load(args.config)
	logging.getLogger(__name__).info(
		'scale=%s classes=%s', cfg.scale, ', '.join(cfg.classes)
	)

	signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
	try:
		Daemon(cfg).run()
	except ipc.IPCError as e:
		print(f'lilypad: {e}', file=sys.stderr)
		return 1
	except KeyboardInterrupt:
		return 0
	return 1  # event socket closed: Hyprland went away


if __name__ == '__main__':
	sys.exit(main())
