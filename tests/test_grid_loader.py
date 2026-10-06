"""Tests for loading the IEEE 14-bus grid."""

import pandapower.networks as pn
import pytest

from src import grid_loader


def test_load_ieee14_returns_valid_network() -> None:
    net = grid_loader.load_ieee14()

    assert len(net.bus) == 14
    assert not net.line.empty
    assert not net.load.empty
    assert not net.gen.empty


@pytest.mark.parametrize("element", ["bus", "line", "load", "gen"])
def test_load_ieee14_rejects_missing_required_elements(
    monkeypatch: pytest.MonkeyPatch,
    element: str,
) -> None:
    invalid_net = pn.case14()
    invalid_net[element] = invalid_net[element].iloc[0:0].copy()
    monkeypatch.setattr(pn, "case14", lambda: invalid_net)

    with pytest.raises(ValueError, match=element):
        grid_loader.load_ieee14()
