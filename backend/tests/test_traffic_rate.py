"""Unit tests for the consolidated traffic-rate helper (all the bug cases)."""

from datetime import datetime, timedelta

from traffic_rate import compute_traffic_rate, RateInput


T0 = datetime(2026, 7, 6, 12, 0, 0)


def _prev(rx_bytes=0, tx_bytes=0, t=T0, last_rx=0.0, last_tx=0.0):
    return RateInput(rx_bytes, tx_bytes, t, last_rx, last_tx)


def test_offline_forces_zero_and_resyncs():
    # Offline ONU whose counters are frozen but last rate was high.
    prev = _prev(rx_bytes=1000, tx_bytes=2000, last_rx=50000, last_tx=40000)
    r = compute_traffic_rate(prev, 1000, 2000, T0 + timedelta(seconds=5), is_online=False)
    assert (r.rx_kbps, r.tx_kbps) == (0.0, 0.0)
    # snapshot resynced + last rate cleared so a return-online starts clean
    assert r.new_last_rx_kbps == 0.0 and r.new_last_tx_kbps == 0.0
    assert r.new_rx_bytes == 1000 and r.new_timestamp == T0 + timedelta(seconds=5)


def test_normal_movement_computes_kbps():
    # 1,000,000 bytes over 10s => 1e6*8/10/1000 = 800 kbps
    prev = _prev(rx_bytes=0, tx_bytes=0)
    r = compute_traffic_rate(prev, 1_000_000, 500_000, T0 + timedelta(seconds=10), is_online=True)
    assert r.rx_kbps == 800.0
    assert r.tx_kbps == 400.0
    assert r.new_last_rx_kbps == 800.0
    assert r.new_timestamp == T0 + timedelta(seconds=10)


def test_no_spike_when_counter_refreshes_after_idle_polls():
    # Counter unchanged for two 5s polls (held), then jumps by 30s worth of bytes.
    # Because timestamp only advances on movement, the rate is computed over the
    # true 30s window, NOT the 5s poll gap -> no 6x spike.
    prev = _prev(rx_bytes=0, tx_bytes=0, last_rx=100.0, last_tx=0.0)
    # poll 1 @ +5s: no change -> hold 100
    r1 = compute_traffic_rate(prev, 0, 0, T0 + timedelta(seconds=5), is_online=True)
    assert r1.rx_kbps == 100.0 and r1.new_timestamp is None  # timestamp NOT advanced
    # poll 2 @ +30s: counter finally moves by 3,000,000 bytes
    r2 = compute_traffic_rate(prev, 3_000_000, 0, T0 + timedelta(seconds=30), is_online=True)
    # 3e6*8/30/1000 = 800 kbps (correct), not 4800 (would be the 5s-window spike)
    assert r2.rx_kbps == 800.0


def test_idle_online_decays_to_zero_after_hold_window():
    # Online but no counter movement beyond the hold window -> rate must drop to 0
    prev = _prev(rx_bytes=100, tx_bytes=100, last_rx=500.0, last_tx=500.0)
    r = compute_traffic_rate(prev, 100, 100, T0 + timedelta(seconds=90), is_online=True)
    assert (r.rx_kbps, r.tx_kbps) == (0.0, 0.0)
    assert r.new_last_rx_kbps == 0.0


def test_idle_within_hold_window_holds_last():
    prev = _prev(rx_bytes=100, tx_bytes=100, last_rx=500.0, last_tx=300.0)
    r = compute_traffic_rate(prev, 100, 100, T0 + timedelta(seconds=20), is_online=True)
    assert (r.rx_kbps, r.tx_kbps) == (500.0, 300.0)
    assert r.new_timestamp is None  # unchanged


def test_counter_reset_guarded_per_direction():
    # rx counter reset (went down) but tx advanced normally over 10s.
    prev = _prev(rx_bytes=5_000_000, tx_bytes=0, last_rx=100.0)
    r = compute_traffic_rate(prev, 10, 1_000_000, T0 + timedelta(seconds=10), is_online=True)
    assert r.rx_kbps == 0.0            # reset direction -> 0, not garbage/huge
    assert r.tx_kbps == 800.0          # good direction preserved


def test_spike_above_cap_holds_previous_not_zero():
    prev = _prev(rx_bytes=0, tx_bytes=0, last_rx=250.0, last_tx=120.0)
    # 10 GB in 1s -> absurd, above 1.5Gbps cap
    r = compute_traffic_rate(prev, 10_000_000_000, 0, T0 + timedelta(seconds=1), is_online=True)
    assert r.rx_kbps == 250.0 and r.tx_kbps == 120.0   # held, not 0
    assert r.new_rx_bytes == 10_000_000_000            # counters resynced


def test_stale_gap_resyncs_to_zero():
    prev = _prev(rx_bytes=0, tx_bytes=0, last_rx=900.0, t=T0)
    r = compute_traffic_rate(prev, 9_000_000, 0, T0 + timedelta(seconds=600), is_online=True)
    assert (r.rx_kbps, r.tx_kbps) == (0.0, 0.0)
    assert r.new_timestamp == T0 + timedelta(seconds=600)


def test_zero_or_negative_time_diff_holds():
    prev = _prev(rx_bytes=0, tx_bytes=0, last_rx=42.0)
    r = compute_traffic_rate(prev, 999, 999, T0, is_online=True)  # same instant
    assert r.rx_kbps == 42.0
    assert r.new_rx_bytes is None


def test_apply_to_snapshot():
    class Snap:
        rx_bytes = tx_bytes = 0
        timestamp = T0
        last_rx_kbps = last_tx_kbps = 0.0
    prev = _prev(rx_bytes=0, tx_bytes=0)
    r = compute_traffic_rate(prev, 1_000_000, 0, T0 + timedelta(seconds=10), is_online=True)
    s = Snap()
    r.apply_to(s)
    assert s.rx_bytes == 1_000_000 and s.last_rx_kbps == 800.0
