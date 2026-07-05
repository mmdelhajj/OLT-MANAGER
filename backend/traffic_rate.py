"""Single source of truth for per-ONU traffic-rate computation.

Historically the rate math `(bytes_diff*8)/time_diff/1000` was copy-pasted into
~5 places (polling loop, SaaS poll, /api/traffic/all, per-OLT endpoint, the
WebSocket loop) that disagreed on the important edge cases, producing:
  * offline / idle ONUs showing their last-known rate forever,
  * ~6x spikes then zeros when the counter timestamp was advanced every poll
    instead of only when the counter actually moved,
  * stale rates written into history as false plateaus.

`compute_traffic_rate()` centralises the correct behaviour. It is a pure
function (no DB/IO) so it is fully unit-tested.

Key rules:
  * OFFLINE ONU  -> hard 0, and resync stored counters so it starts clean when
    it comes back online.
  * Counter reset (reboot / OLT reboot) -> guard each direction independently;
    treat as no movement this cycle.
  * Counter unchanged (OLT refreshes octets ~every 30s but we poll faster) ->
    hold the last computed rate, but only within `hold_window` seconds; beyond
    that the traffic has genuinely stopped, so decay to 0 (fixes idle-forever).
  * Only advance the stored byte counters + timestamp when the counter actually
    moved (or on resync), so the byte delta and time delta always cover the same
    window -> no 6x spike.
  * Implausible spike above `max_kbps` -> hold the previous value (don't dip to
    0), and resync counters.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class RateInput:
    """Previous snapshot state (duck-typed from TrafficSnapshot or a dict)."""
    rx_bytes: int
    tx_bytes: int
    timestamp: object            # datetime
    last_rx_kbps: float = 0.0
    last_tx_kbps: float = 0.0


@dataclass
class RateResult:
    rx_kbps: float
    tx_kbps: float
    # Snapshot fields to persist. None => leave the snapshot unchanged.
    new_rx_bytes: Optional[int] = None
    new_tx_bytes: Optional[int] = None
    new_timestamp: object = None
    new_last_rx_kbps: Optional[float] = None
    new_last_tx_kbps: Optional[float] = None

    def apply_to(self, snap) -> None:
        """Persist the computed updates onto a TrafficSnapshot-like object."""
        if self.new_rx_bytes is not None:
            snap.rx_bytes = self.new_rx_bytes
        if self.new_tx_bytes is not None:
            snap.tx_bytes = self.new_tx_bytes
        if self.new_timestamp is not None:
            snap.timestamp = self.new_timestamp
        if self.new_last_rx_kbps is not None:
            snap.last_rx_kbps = self.new_last_rx_kbps
        if self.new_last_tx_kbps is not None:
            snap.last_tx_kbps = self.new_last_tx_kbps


MAX_VALID_KBPS = 1_500_000   # 1.5 Gbps — above any real ONU capacity
STALE_AFTER_S = 300          # gap larger than this => resync, don't trust
HOLD_WINDOW_S = 60           # hold last rate at most this long between counter moves


def compute_traffic_rate(
    prev: RateInput,
    curr_rx_bytes: int,
    curr_tx_bytes: int,
    curr_time,
    is_online: bool,
    *,
    max_kbps: int = MAX_VALID_KBPS,
    stale_after: float = STALE_AFTER_S,
    hold_window: float = HOLD_WINDOW_S,
) -> RateResult:
    # Offline: hard zero + resync so the next online sample is clean.
    if not is_online:
        return RateResult(0.0, 0.0, curr_rx_bytes, curr_tx_bytes, curr_time, 0.0, 0.0)

    time_diff = (curr_time - prev.timestamp).total_seconds()
    if time_diff <= 0:
        # Clock went backwards / same instant — hold last, change nothing.
        return RateResult(float(prev.last_rx_kbps or 0), float(prev.last_tx_kbps or 0))

    rx_diff = curr_rx_bytes - prev.rx_bytes
    tx_diff = curr_tx_bytes - prev.tx_bytes
    # Per-direction counter-reset guard (an ONU reboot may reset only one).
    if rx_diff < 0:
        rx_diff = 0
    if tx_diff < 0:
        tx_diff = 0

    # Gap too large — resync and zero (rate over a huge window is meaningless).
    if time_diff > stale_after:
        return RateResult(0.0, 0.0, curr_rx_bytes, curr_tx_bytes, curr_time, 0.0, 0.0)

    # Counter hasn't refreshed yet this cycle.
    if rx_diff == 0 and tx_diff == 0:
        if time_diff <= hold_window:
            # Hold last rate; do NOT advance timestamp (keeps the window intact).
            return RateResult(float(prev.last_rx_kbps or 0), float(prev.last_tx_kbps or 0))
        # No movement for too long => traffic genuinely stopped.
        return RateResult(0.0, 0.0, new_last_rx_kbps=0.0, new_last_tx_kbps=0.0)

    # Real movement over the full interval since the last change.
    rx_kbps = round((rx_diff * 8) / time_diff / 1000, 2)
    tx_kbps = round((tx_diff * 8) / time_diff / 1000, 2)

    # Implausible spike -> hold previous value, resync counters (avoid 0 dip).
    if rx_kbps > max_kbps or tx_kbps > max_kbps:
        return RateResult(
            float(prev.last_rx_kbps or 0), float(prev.last_tx_kbps or 0),
            new_rx_bytes=curr_rx_bytes, new_tx_bytes=curr_tx_bytes, new_timestamp=curr_time,
        )

    return RateResult(
        rx_kbps, tx_kbps,
        new_rx_bytes=curr_rx_bytes, new_tx_bytes=curr_tx_bytes, new_timestamp=curr_time,
        new_last_rx_kbps=rx_kbps, new_last_tx_kbps=tx_kbps,
    )
