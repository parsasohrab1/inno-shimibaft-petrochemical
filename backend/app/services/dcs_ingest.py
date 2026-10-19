"""DCS / Historian / LIMS ingestion — NOT IMPLEMENTED.

The SPRO proposal letter (ref. 14050616001) describes Module 1 as ingesting
real-time data from the plant DCS and from the Historian. Connecting to a
real DCS (e.g. via OPC UA/DA, Modbus, or a vendor-specific historian API
such as AspenTech IP.21, Honeywell PHD, Yokogawa Exaquantum) and to the
plant LIMS is a significant, site-specific integration effort that is
explicitly out of scope for this scaffold.

This module exists as the single place that real integration code would
live, so the rest of the codebase (``services/process_intelligence.py`` and
friends) can be written against a stable interface from day one.

Until a real connector is implemented, every function here raises
``NotImplementedError`` — callers must fall back to the seeded sample data
in ``backend/app/seed.py`` (see ``routers/process_intelligence.py`` for the
pattern) rather than silently returning fabricated "live" numbers.
"""
from __future__ import annotations


def pull_dcs_snapshot(tag_ids: list[str]) -> dict[str, float]:
    """Pull current values for the given DCS tags.

    TODO: implement a real OPC UA/Modbus/vendor-historian client once the
    client confirms which protocol and credentials are available on-site.
    """
    raise NotImplementedError("DCS connectivity is not implemented in this scaffold")


def pull_historian_range(tag_id: str, start_iso: str, end_iso: str):
    """Pull a time range of historized samples for one tag.

    TODO: implement against the plant's real Historian (IP.21 / PHD /
    Exaquantum / PI, etc.) once an endpoint and read credentials exist.
    """
    raise NotImplementedError("Historian connectivity is not implemented in this scaffold")


def pull_lab_results(product: str, since_iso: str):
    """Pull recent LIMS/lab results for a product.

    TODO: implement against the plant's real LIMS once an export format or
    API is confirmed.
    """
    raise NotImplementedError("LIMS connectivity is not implemented in this scaffold")
