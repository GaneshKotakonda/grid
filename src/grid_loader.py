"""Load and validate standard power-grid test networks."""

import pandapower.networks as pn
from pandapower.auxiliary import pandapowerNet


REQUIRED_ELEMENTS = ("bus", "line", "load", "gen")


def load_ieee14() -> pandapowerNet:
    """Return pandapower's IEEE 14-bus network after basic validation."""
    net = pn.case14()

    for element in REQUIRED_ELEMENTS:
        table = getattr(net, element, None)
        if table is None or table.empty:
            raise ValueError(f"IEEE 14-bus network has no {element} elements")

    return net
