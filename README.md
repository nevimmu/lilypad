# lilypad

Hyprland daemon: when a chosen program (terminal by default) is the only tiled
window in a workspace, it is floated, resized and centered.
When a second tiled window appears (spawned or moved in), it goes back
to tiling. Closing/moving the other window floats it again.

## Install

```bash
pipx install -e .
```

Add to `hyprland.conf`:

```
exec-once = lilypad
```

## Config

Created on first run at `~/.config/lilypad/config.toml`:

```toml
scale = 0.71
classes = ["kitty", "foot", "Alacritty", "org.wezfurlong.wezterm", "com.mitchellh.ghostty"]
```

Restart `lilypad` after editing. Find a window's class with `hyprctl clients | grep class`.

Notes: only tiled windows count as "other windows"; fullscreen and pinned windows are
skipped; a window you manually tile is left alone until another tiled window joins it.

## Tests

```bash
pip install -e '.[test]' && pytest
```

## AI assistance

This project was built with the help of AI tools. As an experienced developer, 
I use AI to improve productivity and explore solutions. Not to take all the decisions. 
I review and understand the code I ship.