"""Reproduce two audited 2026 Singapore Q3 comparison figures.
Run: .venv/bin/python singapore_q3.py
Public broadcast telemetry: no steering, brake pressure, fuel or energy modes.
"""
from pathlib import Path
import json
import pickle
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import fastf1

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'outputs'
CACHE = ROOT / '.cache'
YEAR, LENGTH, GAP_LIMIT = 2026, 4927.0, 0.6
COLORS = {'VER': '#2268bd', 'LEC': '#d52b39'}
CHANNELS = ['Speed', 'Throttle', 'Brake', 'nGear', 'RPM', 'DRS']
EXPECTED = {'VER': 91.373, 'LEC': 91.427}


def plain(value):
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if pd.isna(value):
        return None
    if isinstance(value, (pd.Timestamp, pd.Timedelta)):
        return str(value)
    if isinstance(value, np.generic):
        return value.item()
    return value


def integrate(t, v):
    # km/h -> m/s, trapezoidal integration. Distance is derived, never raw.
    return np.r_[0.0, np.cumsum(np.diff(t) * (v[:-1] + v[1:]) / 7.2)]


def load_session():
    (CACHE / 'fastf1').mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(CACHE / 'fastf1'))
    stored = CACHE / 'session.pkl'
    if stored.exists():
        # Only load this locally generated cache, never an untrusted pickle.
        return pickle.loads(stored.read_bytes())
    session = fastf1.get_session(YEAR, 'Singapore', 'Q')
    session.load()
    stored.write_bytes(pickle.dumps(session))
    return session


def prepare(lap, export_prefix=None):
    export_prefix = export_prefix or lap.Driver
    raw = lap.get_car_data()
    raw.to_csv(OUT / f'{export_prefix}_car_original.csv', index=False)
    lap.get_pos_data().to_csv(OUT / f'{export_prefix}_position_original.csv', index=False)
    t = raw.Time.dt.total_seconds().to_numpy()
    duration = lap.LapTime.total_seconds()
    checks = {
        'samples': len(raw), 'nulls': raw.isna().sum().to_dict(),
        'source_counts': raw.Source.value_counts().to_dict(),
        'duplicate_timestamps': int(raw.Date.duplicated().sum()),
        'nonincreasing_timestamps': int((np.diff(t) <= 0).sum()),
        'median_dt_s': float(np.median(np.diff(t))),
        'maximum_dt_s': float(np.max(np.diff(t))),
        'first_sample_s': float(t[0]), 'last_sample_s': float(t[-1]),
        'channel_ranges': {c: [raw[c].min(), raw[c].max()] for c in CHANNELS},
        'long_gap_count': int((np.diff(t) > GAP_LIMIT).sum()),
        'range_invalid_counts': {
            'Speed': int((~raw.Speed.between(0, 400)).sum()),
            'Throttle': int((~raw.Throttle.between(0, 100)).sum()),
            'nGear': int((~raw.nGear.between(0, 8)).sum()),
            'RPM': int((~raw.RPM.between(0, 20000)).sum()),
            'Brake': int((~raw.Brake.isin([False, True])).sum()),
        },
    }
    if any(raw[CHANNELS + ['Date', 'Time']].isna().any()) or checks['duplicate_timestamps'] or checks['nonincreasing_timestamps'] or any(checks['range_invalid_counts'].values()):
        raise ValueError(f'{lap.Driver}: invalid source samples; inspect exports before plotting')
    if not (raw.Source == 'car').all():
        raise ValueError('Expected original car-stream timestamps')
    padded = lap.get_car_data(pad=1)
    tp = padded.Time.dt.total_seconds().to_numpy()
    if tp[0] > 0 or tp[-1] < duration:
        raise ValueError('Lap boundaries are not bracketed by observed samples')
    edges_t = np.r_[0, t, duration]
    speed = np.interp(edges_t, tp, padded.Speed)
    distance = integrate(edges_t, speed)
    sector_t = np.r_[0, np.cumsum([lap[c].total_seconds() for c in ['Sector1Time', 'Sector2Time', 'Sector3Time']])]
    if abs(sector_t[-1] - duration) > .003:
        raise ValueError('Sector sum disagrees with official lap time')
    # Insert timing-sector knots explicitly so inverse interpolation preserves anchors.
    knotted_t = np.unique(np.r_[edges_t, sector_t])
    distance = np.interp(knotted_t, edges_t, distance)
    edges_t = knotted_t
    checks['integrated_length_m'] = float(distance[-1])
    checks['fastf1_add_distance_length_m'] = float(raw.add_distance().Distance.iloc[-1])
    checks['boundary_samples_added'] = 2
    return {'export_prefix': export_prefix, 'lap': lap, 'raw': raw, 't': t, 'edge_t': edges_t, 'distance': distance,
            'sector_t': sector_t, 'sector_d': np.interp(sector_t, edges_t, distance),
            'duration': duration, 'quality': checks}


def add_coordinates(data, anchors):
    data['x_edge'] = np.interp(data['distance'], data['sector_d'], anchors)
    data['x'] = np.interp(data['t'], data['edge_t'], data['x_edge'])
    data['x_whole'] = data['distance'] / data['distance'][-1] * LENGTH
    gaps = np.flatnonzero(np.diff(data['t']) > GAP_LIMIT)
    data['gaps'] = [[float(data['x'][i]), float(data['x'][i + 1]), float(data['t'][i]), float(data['t'][i + 1])] for i in gaps]
    data['quality']['long_gaps_distance_time'] = data['gaps']
    processed = data['raw'].copy()
    processed['ElapsedTime_s'] = data['t']
    processed['TrapezoidalDistance_m'] = np.interp(data['t'], data['edge_t'], data['distance'])
    processed['SectorAlignedDistance_m'] = data['x']
    processed['WholeLapNormalizedDistance_m'] = np.interp(data['t'], data['edge_t'], data['x_whole'])
    processed.to_csv(OUT / f'{data["export_prefix"]}_derived.csv', index=False)


def mask_gaps(grid, value, datasets):
    value = value.copy()
    for d in datasets.values():
        for left, right, _, _ in d['gaps']:
            value[(grid > left) & (grid < right)] = np.nan
    return value


def trace(ax, data, channel, detail=False, color=None, linestyle='-'):
    color = color or COLORS[data['lap'].Driver]
    x = data['x']
    y = data['raw'][channel].astype(float).to_numpy()
    # Break lines at long missing intervals; keep observed endpoints as dots.
    xx, yy = [], []
    for i in range(len(x)):
        if i and data['t'][i] - data['t'][i - 1] > GAP_LIMIT:
            xx.append(np.nan); yy.append(np.nan)
        xx.append(x[i]); yy.append(y[i])
    discrete = channel in ['Brake', 'nGear', 'DRS']
    ax.plot(xx, yy, color=color, linestyle=linestyle, lw=1.45,
            drawstyle='steps-post' if discrete else 'default')
    ax.scatter(x, y, s=14 if detail else 4, color=color, zorder=4, alpha=.85)


def decorate(axes, datasets, corners, lo, hi, anchor_d):
    for ax in axes:
        ax.set_xlim(lo, hi)
        ax.grid(axis='y', color='#d6dce3', lw=.6)
        ax.spines[['top', 'right']].set_visible(False)
        for d in datasets.values():
            for left, right, _, _ in d['gaps']:
                if right >= lo and left <= hi:
                    ax.axvspan(left, right, color='#888888', alpha=.10, zorder=0)
        for _, c in corners.iterrows():
            if lo <= c.Distance <= hi:
                ax.axvline(c.Distance, color='#aeb8c3', lw=.65, alpha=.6)
        for boundary in anchor_d[1:-1]:
            ax.axvline(boundary, color='#616a76', lw=.9, ls='--')
    for _, c in corners.iterrows():
        if lo <= c.Distance <= hi:
            axes[0].text(c.Distance, 1.025, f'T{int(c.Number)}{c.Letter}',
                         transform=axes[0].get_xaxis_transform(), ha='center', fontsize=8)
    axes[-1].set_xlabel('Derived distance from start / finish (m) — normalized within timing sectors', fontsize=10)


def phases(data, center):
    r, x = data['raw'], data['x']
    window = np.flatnonzero((x >= center - 100) & (x <= center + 100))
    apex = window[np.argmin(r.Speed.to_numpy()[window])]
    entries = np.flatnonzero((x >= center - 240) & (np.arange(len(x)) < apex) & r.Brake.to_numpy() & ~np.r_[False, r.Brake.to_numpy()[:-1]])
    if not len(entries):
        raise ValueError('No T7 brake-on transition found')
    entry = entries[-1]
    exits = np.flatnonzero((np.arange(len(x)) > apex) & (x <= center + 220) & (r.Throttle.to_numpy() >= 95))
    exit_i = next(i for i in exits if np.all(r.Throttle.to_numpy()[i:np.searchsorted(data['t'], data['t'][i] + .5) + 1] >= 95))
    return {'entry_bracket_m': [float(x[entry - 1]), float(x[entry])],
            'entry_bracket_s': [float(data['t'][entry - 1]), float(data['t'][entry])],
            'apex_proxy_m': float(x[apex]), 'minimum_observed_speed_kmh': float(r.Speed.iloc[apex]),
            'exit_proxy_m': float(x[exit_i]), 'exit_proxy_time_s': float(data['t'][exit_i]),
            'gear_at_minimum': int(r.nGear.iloc[apex])}


def main():
    OUT.mkdir(exist_ok=True)
    s = load_session()
    q3 = s.laps.split_qualifying_sessions()[2]
    if q3 is None:
        raise ValueError('Q3 unavailable')
    candidates = q3.pick_drivers(['VER', 'LEC'])
    candidates.to_csv(OUT / 'q3_candidates.csv', index=False)
    data = {}
    for drv in ['VER', 'LEC']:
        lap = candidates.pick_drivers(drv).pick_fastest()
        if not lap.IsAccurate or bool(lap.Deleted) or lap.FastF1Generated or lap.TrackStatus != '1' or pd.notna(lap.PitInTime) or pd.notna(lap.PitOutTime):
            raise ValueError(f'{drv}: fastest Q3 lap failed validity checks')
        if abs(lap.LapTime.total_seconds() - EXPECTED[drv]) > .0005:
            raise ValueError('Loaded lap differs from verified official results')
        data[drv] = prepare(lap)
    # Match timing sector boundaries, not braking events: preserve driving differences.
    anchors = data['VER']['sector_d'] / data['VER']['distance'][-1] * LENGTH
    for d in data.values():
        add_coordinates(d, anchors)
    stored_circuit = CACHE / 'circuit.pkl'
    ci = pickle.loads(stored_circuit.read_bytes()) if stored_circuit.exists() else s.get_circuit_info()
    if ci is None:
        raise ValueError('Circuit markers unavailable; do not invent turn locations')
    corners = ci.corners.copy()
    p = data['VER']['lap'].get_pos_data()
    xy = p[['X', 'Y']].to_numpy()
    indices = [int(np.argmin(((xy - c[['X', 'Y']].to_numpy(dtype=float)) ** 2).sum(axis=1))) for _, c in corners.iterrows()]
    pos_t = p.Time.dt.total_seconds().to_numpy()[indices]
    corners['Distance'] = np.interp(pos_t, data['VER']['edge_t'], data['VER']['x_edge'])
    corners.to_csv(OUT / 'corner_markers_approximate.csv', index=False)
    grid = np.unique(np.r_[np.arange(0, LENGTH, 5), anchors, LENGTH])
    delta = np.interp(grid, data['LEC']['x_edge'], data['LEC']['edge_t']) - np.interp(grid, data['VER']['x_edge'], data['VER']['edge_t'])
    whole_delta = np.interp(grid, data['LEC']['x_whole'], data['LEC']['edge_t']) - np.interp(grid, data['VER']['x_whole'], data['VER']['edge_t'])
    pd.DataFrame({'Distance_m': grid, 'Delta_LEC_minus_VER_sector_aligned_s': delta,
                  'Delta_LEC_minus_VER_whole_lap_normalized_s': whole_delta,
                  'Inside_long_gap': np.isnan(mask_gaps(grid, delta, data))}).to_csv(OUT / 'delta_estimates.csv', index=False)
    official = data['LEC']['sector_t'] - data['VER']['sector_t']
    assert np.allclose(np.interp(anchors, grid, delta), official, atol=1e-9)
    center = float(corners.loc[corners.Number == 7, 'Distance'].iloc[0])
    phase = {drv: phases(d, center) for drv, d in data.items()}
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'figure.facecolor': '#f7f9fc', 'axes.facecolor': '#ffffff'})
    for detail, name in [(False, '01_full_lap'), (True, '02_turn7_detail')]:
        fig, axes = plt.subplots(6, 1, figsize=(15, 12), sharex=True, gridspec_kw={'height_ratios': [2.3, 1.3, 1, 1, 1.2, 1.7]})
        fig.subplots_adjust(left=.09, right=.965, top=.86, bottom=.20, hspace=.15)
        title = 'TURN 7 | braking, speed minimum and throttle recovery' if detail else 'SINGAPORE 2026 | fastest Q3 laps'
        fig.suptitle(title, fontsize=20, fontweight='bold', x=.09, ha='left', y=.965)
        fig.text(.09, .928, 'Grand Prix qualifying · 10 October 2026 · VER lap 11: 1:31.373 · LEC lap 24: 1:31.427 · official gap +0.054 s', fontsize=11)
        fig.text(.09, .903, 'Blue: Verstappen   Red: Leclerc   • original car-stream samples   Lines: continuous linear / discrete held   Grey: sample gaps >0.6 s', fontsize=10)
        for d in data.values():
            for ax, ch in zip(axes[:5], ['Speed', 'Throttle', 'Brake', 'nGear', 'RPM']):
                trace(ax, d, ch, detail)
        for ax, label in zip(axes[:5], ['Speed\n(km/h)', 'Throttle\n(%)', 'Brake\n(on / off)', 'Gear', 'RPM\n(rev/min)']):
            ax.set_ylabel(label)
        axes[1].set_ylim(-5, 105)
        axes[2].set_yticks([0, 1], ['off', 'on']); axes[2].set_ylim(-.15, 1.15)
        axes[3].set_yticks([2, 4, 6, 8])
        axes[5].plot(grid, mask_gaps(grid, delta, data), color='#263446', lw=1.6, label='Sector-aligned estimate')
        axes[5].plot(grid, mask_gaps(grid, whole_delta, data), color='#987024', lw=1.1, ls='--', label='Whole-lap normalization sensitivity')
        axes[5].fill_between(grid, mask_gaps(grid, delta, data), mask_gaps(grid, whole_delta, data), color='#987024', alpha=.10)
        axes[5].axhline(0, color='#a0a0a0', lw=.7)
        axes[5].scatter(anchors, official, color='#263446', marker='D', s=25, zorder=5)
        axes[5].set_ylabel('Estimated Δt (s)\nLEC − VER')
        fig.legend(*axes[5].get_legend_handles_labels(), loc='upper right', bbox_to_anchor=(.965, .894), fontsize=9, frameon=False, ncol=2)
        lo, hi = (center - 250, center + 145) if detail else (0, LENGTH)
        decorate(axes, data, corners, lo, hi, anchors)
        if detail:
            visible = (grid >= lo) & (grid <= hi)
            local_values = np.r_[delta[visible], whole_delta[visible]]
            axes[5].set_ylim(float(local_values.min()) - .06, float(local_values.max()) + .08)
            for row, drv in enumerate(['VER', 'LEC']):
                ph = phase[drv]
                y = .96 - row * .14
                a, b = ph['entry_bracket_m']
                axes[0].axvspan(a, b, color=COLORS[drv], alpha=.14)
                for value, label in [(b, 'E'), (ph['apex_proxy_m'], 'A*'), (ph['exit_proxy_m'], 'X')]:
                    for ax in axes[:5]:
                        ax.axvline(value, color=COLORS[drv], alpha=.35, ls=':', lw=.85)
                    axes[0].text(value, y, f'{drv} {label}', color=COLORS[drv], fontsize=9, ha='center', transform=axes[0].get_xaxis_transform())
            axes[0].set_ylim(90, 345)
            fig.text(.09, .055, 'E: brake-on lies within the shaded last-off / first-on interval. A*: lowest observed speed, not a measured geometric apex.\nX: first ≥95% throttle sample sustained for ≥0.5 s; operational exit proxy, not the geometric corner exit.\nVER’s entry interval contains a 1.08 s missing interval: this comparison cannot establish who braked later.', fontsize=10, linespacing=1.5)
        else:
            for x, y, text in zip(anchors[1:], official[1:], ['S1 +0.023', 'S2 cumulative −0.107', 'Finish +0.054']):
                axes[5].annotate(text, (x, y), xytext=(-6, 10), textcoords='offset points', ha='right', fontsize=8)
            fig.text(.09, .055, 'Both: SOFT · fresh set · TyreLife 2 (includes out-lap). LEC’s lap began 590.337 s after VER’s: track evolution uncontrolled.\nFuel, tyre pressures/temperatures, traffic effects, damage, setup and energy/active-aero modes unknown.\nDistance and delta are derived. Timing-sector anchors are enforced; method spread is sensitivity, not a confidence interval.', fontsize=10, linespacing=1.5)
        fig.savefig(OUT / f'{name}.png', dpi=180)
        fig.savefig(OUT / f'{name}.svg')
        plt.close(fig)
    weather = {drv: plain(d['lap'].get_weather_data().to_dict()) for drv, d in data.items()}
    metadata_keys = ['Driver', 'LapNumber', 'LapTime', 'LapStartTime', 'LapStartDate', 'Compound', 'TyreLife', 'FreshTyre', 'IsAccurate', 'Deleted', 'FastF1Generated', 'TrackStatus']
    audit = {'session': '2026 Singapore Grand Prix Qualifying Q3', 'fastf1_version': fastf1.__version__,
             'python_version': sys.version, 'distance_length_nominal_m': LENGTH, 'long_gap_threshold_s': GAP_LIMIT,
             'laps': {drv: plain(d['lap'][metadata_keys].to_dict()) for drv, d in data.items()},
             'quality': {drv: plain(d['quality']) for drv, d in data.items()}, 'weather': weather,
             'official_cumulative_delta_s': official.tolist(), 'sector_distance_anchors_m': anchors.tolist(),
             'turn7_phase_proxies': phase, 'maximum_alignment_method_spread_s': float(np.max(np.abs(delta - whole_delta)))}
    (OUT / 'audit.json').write_text(json.dumps(audit, indent=2) + '\n')
    s.race_control_messages.to_csv(OUT / 'race_control_messages.csv', index=False)
    s.weather_data.to_csv(OUT / 'weather_session.csv', index=False)
    pd.DataFrame({drv: np.diff(d['sector_t']) for drv, d in data.items()}, index=['S1', 'S2', 'S3']).to_csv(OUT / 'official_sector_times.csv')
    print(json.dumps(audit, indent=2))


if __name__ == '__main__':
    main()
