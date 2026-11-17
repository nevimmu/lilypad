from lilypad.config import Config
from lilypad.daemon import Daemon, to_commands
from lilypad.logic import Float, Tile
from test_logic import mon, win


def test_to_commands():
	assert to_commands(Tile('0x1')) == [
		"hl.dsp.window.float({ action = 'disable', window = 'address:0x1' })"
	]
	cmds = to_commands(Float('0x1', 10, 20, 300, 400))
	assert cmds == [
		"hl.dsp.window.float({ action = 'enable', window = 'address:0x1' })",
		"hl.dsp.window.resize({ x = 300, y = 400, exact = true, window = 'address:0x1' })",
		"hl.dsp.window.move({ x = 10, y = 20, exact = true, window = 'address:0x1' })",
	]


def test_run_once_dispatches():
	sent = []
	clients = [[win('0x1')]]
	d = Daemon(Config(classes=['kitty']), lambda: clients[0], lambda: [mon()], sent.append, lambda: 2)
	d.run_once()
	assert sent and "action = 'enable'" in sent[0][0]
	clients[0] = [win('0x1', floating=True), win('0x2', cls='x')]
	sent.clear()
	d.run_once()
	assert len(sent) == 1 and "action = 'disable'" in sent[0][0]
	assert 'window.swap' in sent[0][1] and "target = 'address:0x2'" in sent[0][1]


def test_no_swap_when_force_split_zero():
	t = Tile('0x1', swap_with='0x2')
	assert len(to_commands(t, 0)) == 1
	assert len(to_commands(t, 2)) == 2
