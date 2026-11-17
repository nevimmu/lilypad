from lilypad.config import Config
from lilypad.logic import Float, State, Tile, geometry, reconcile

CFG = Config(scale=0.71, classes=['kitty'])


def mon(**kw):
	m = dict(id=0, x=0, y=0, width=1920, height=1080, scale=1, transform=0, reserved=[0, 0, 0, 0])
	m.update(kw)
	return m


def win(addr, cls='kitty', ws=1, floating=False, monitor=0, **kw):
	w = dict(address=addr, mapped=True, hidden=False, floating=floating, monitor=monitor,
			 workspace={'id': ws}, **{'class': cls}, fullscreen=0, pinned=False)
	w.update(kw)
	return w


def test_geometry_plain():
	assert geometry(mon(), 0.71) == (278, 156, 1363, 767)


def test_geometry_reserved_scale_rotation():
	m = mon(x=100, y=50, width=1920, height=1080, scale=2, transform=1, reserved=[0, 30, 0, 0])
	# rotated: 1080x1920 -> /2 = 540x960; usable 540x930
	x, y, w, h = geometry(m, 0.5)
	assert (w, h) == (270, 465)
	assert x == 100 + (540 - 270) // 2
	assert y == 80 + (930 - 465) // 2 or y == round(80 + (930 - 465) / 2)


def test_lone_terminal_floats():
	s = State()
	acts = reconcile([win('a')], [mon()], s, CFG)
	assert acts == [Float('a', 278, 156, 1363, 767)]
	assert 'a' in s.managed


def test_non_matching_ignored():
	assert reconcile([win('a', cls='firefox')], [mon()], State(), CFG) == []


def test_second_window_retiles_then_refloats():
	s = State()
	reconcile([win('a')], [mon()], s, CFG)
	acts = reconcile([win('a', floating=True), win('b', cls='firefox')], [mon()], s, CFG)
	assert acts == [Tile('a', swap_with='b')]
	# firefox closes, kitty tiled again -> floats again
	acts = reconcile([win('a')], [mon()], s, CFG)
	assert [type(a) for a in acts] == [Float]


def test_other_floating_window_does_not_retile():
	s = State()
	reconcile([win('a')], [mon()], s, CFG)
	acts = reconcile([win('a', floating=True), win('p', cls='pavucontrol', floating=True)], [mon()], s, CFG)
	assert acts == []


def test_other_workspace_ignored():
	s = State()
	reconcile([win('a')], [mon()], s, CFG)
	assert reconcile([win('a', floating=True), win('b', cls='x', ws=2)], [mon()], s, CFG) == []


def test_manual_tile_respected_until_second_window():
	s = State()
	reconcile([win('a')], [mon()], s, CFG)
	assert reconcile([win('a')], [mon()], s, CFG) == []  # user tiled it
	assert 'a' in s.manual
	# 2nd window arrives, then leaves -> floats again
	assert reconcile([win('a'), win('b', cls='x')], [mon()], s, CFG) == []
	assert 'a' not in s.manual
	assert len(reconcile([win('a')], [mon()], s, CFG)) == 1


def test_fullscreen_and_pinned_skipped():
	assert reconcile([win('a', fullscreen=2)], [mon()], State(), CFG) == []
	assert reconcile([win('a', pinned=True)], [mon()], State(), CFG) == []


def test_unmapped_ignored():
	s = State()
	reconcile([win('a')], [mon()], s, CFG)
	# tiled newcomer not yet mapped -> no retile
	assert reconcile([win('a', floating=True), win('b', mapped=False)], [mon()], s, CFG) == []


def test_two_managed_floating_in_same_workspace_both_tile():
	s = State()
	reconcile([win('a', ws=1), win('b', ws=2)], [mon()], s, CFG)
	assert set(s.managed) == {'a', 'b'}
	# b moved into workspace 1, where a is already floating
	acts = reconcile([win('a', floating=True), win('b', floating=True, ws=1)], [mon()], s, CFG)
	assert sorted(a.address for a in acts) == ['a', 'b'] and all(isinstance(a, Tile) for a in acts)
	assert not s.managed
	# both tiled now: nothing more happens
	assert reconcile([win('a'), win('b')], [mon()], s, CFG) == []


def test_special_workspace_has_no_id():
	special = {'address': 'special:scratchpad', 'type': 'special', 'name': 'special:scratchpad'}
	s = State()
	acts = reconcile([win('a', workspace=special)], [mon()], s, CFG)
	assert [type(a) for a in acts] == [Float]
	acts = reconcile([win('a', floating=True, workspace=special),
					  win('b', cls='x', workspace=special)], [mon()], s, CFG)
	assert acts == [Tile('a', swap_with='b')]
