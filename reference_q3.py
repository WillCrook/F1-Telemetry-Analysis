"""Compare each driver's fastest and second-fastest valid Singapore 2026 Q3 laps.
Run: .venv/bin/python reference_q3.py
Reuses the audited channel/coordinate methods from singapore_q3.py.
"""
import json
import pickle
import numpy as np
import pandas as pd
import singapore_q3 as base
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

REFERENCE_COLOR = '#b47914'


def time_label(seconds):
    return f'{int(seconds // 60)}:{seconds % 60:06.3f}'


def main():
    base.OUT.mkdir(exist_ok=True)
    session = base.load_session()
    q3 = session.laps.split_qualifying_sessions()[2]
    if q3 is None:
        raise ValueError('Q3 unavailable')
    all_data, selection = {}, {}
    for drv in ['VER', 'LEC']:
        laps = q3.pick_drivers(drv)
        valid = laps.loc[
            laps.LapTime.notna() & laps.IsAccurate.eq(True) & laps.Deleted.eq(False)
            & laps.FastF1Generated.eq(False) & laps.TrackStatus.eq('1')
            & laps.PitInTime.isna() & laps.PitOutTime.isna()
        ].sort_values('LapTime')
        if len(valid) < 2:
            raise ValueError(f'{drv}: fewer than two valid Q3 flying laps')
        pair = {}
        for role, rank in [('fastest', 0), ('reference', 1)]:
            lap = valid.iloc[rank]
            number = int(lap.LapNumber)
            prefix = f'{drv}_lap{number}'
            pair[role] = base.prepare(lap, export_prefix=prefix)
        if abs(pair['fastest']['duration'] - base.EXPECTED[drv]) > .0005:
            raise ValueError('Fastest lap does not match verified session results')
        # Identify chronological run separately from lap-time ranking.
        ordered = sorted(pair, key=lambda role: pair[role]['lap'].LapStartTime)
        run = {role: ('first Q3 run' if i == 0 else 'final Q3 run') for i, role in enumerate(ordered)}
        for role in pair:
            pair[role]['run'] = run[role]
        all_data[drv] = pair
    # Use the existing VER fastest-lap coordinates for all four laps.
    ver = all_data['VER']['fastest']
    anchors = ver['sector_d'] / ver['distance'][-1] * base.LENGTH
    for pair in all_data.values():
        for d in pair.values():
            base.add_coordinates(d, anchors)
    cached_circuit = base.CACHE / 'circuit.pkl'
    ci = pickle.loads(cached_circuit.read_bytes()) if cached_circuit.exists() else session.get_circuit_info()
    if ci is None:
        raise ValueError('Circuit markers unavailable')
    corners = ci.corners.copy()
    positions = ver['lap'].get_pos_data()
    xy = positions[['X', 'Y']].to_numpy()
    indices = [int(np.argmin(((xy - c[['X', 'Y']].to_numpy(dtype=float)) ** 2).sum(axis=1))) for _, c in corners.iterrows()]
    corners['Distance'] = np.interp(positions.Time.dt.total_seconds().to_numpy()[indices], ver['edge_t'], ver['x_edge'])
    grid = np.unique(np.r_[np.arange(0, base.LENGTH, 5), anchors, base.LENGTH])
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'figure.facecolor': '#f7f9fc', 'axes.facecolor': '#ffffff'})
    summary_rows = []
    for drv, name in [('VER', '03_ver_reference'), ('LEC', '04_lec_reference')]:
        pair = all_data[drv]
        fastest, reference = pair['fastest'], pair['reference']
        delta = np.interp(grid, reference['x_edge'], reference['edge_t']) - np.interp(grid, fastest['x_edge'], fastest['edge_t'])
        whole = np.interp(grid, reference['x_whole'], reference['edge_t']) - np.interp(grid, fastest['x_whole'], fastest['edge_t'])
        official = reference['sector_t'] - fastest['sector_t']
        if not np.allclose(np.interp(anchors, grid, delta), official, atol=1e-9):
            raise ValueError('Delta failed timing-sector anchor check')
        spread = float(np.max(np.abs(delta - whole)))
        pd.DataFrame({'Distance_m': grid, 'Delta_reference_minus_fastest_sector_aligned_s': delta,
                      'Delta_reference_minus_fastest_whole_lap_normalized_s': whole,
                      'Inside_long_gap': np.isnan(base.mask_gaps(grid, delta, pair))}).to_csv(base.OUT / f'{drv}_reference_delta.csv', index=False)
        fig, axes = plt.subplots(6, 1, figsize=(15, 12), sharex=True,
                                 gridspec_kw={'height_ratios': [2.3, 1.3, 1, 1, 1.2, 1.7]})
        fig.subplots_adjust(left=.09, right=.965, top=.83, bottom=.20, hspace=.15)
        full_name = 'MAX VERSTAPPEN' if drv == 'VER' else 'CHARLES LECLERC'
        fig.suptitle(f'{full_name} | fastest vs reference Q3 lap', fontsize=20, fontweight='bold', x=.09, ha='left', y=.965)
        fig.text(.09, .928, 'Singapore Grand Prix qualifying · 10 October 2026 · Reference = second-fastest valid Q3 flying lap', fontsize=11)
        handles = []
        for role, d in pair.items():
            color = base.COLORS[drv] if role == 'fastest' else REFERENCE_COLOR
            style = '-' if role == 'fastest' else '--'
            label = f'{role.capitalize()}: lap {int(d["lap"].LapNumber)}, {time_label(d["duration"])} ({d["run"]})'
            handles.append(Line2D([], [], color=color, ls=style, lw=2, label=label))
            for ax, channel in zip(axes[:5], ['Speed', 'Throttle', 'Brake', 'nGear', 'RPM']):
                base.trace(ax, d, channel, color=color, linestyle=style)
        fig.legend(handles=handles, loc='upper left', bbox_to_anchor=(.082, .916), ncol=2, frameon=False, fontsize=10)
        fig.text(.09, .866, 'Dots: original car samples · Continuous lines: linear display interpolation · Brake/gear: held steps · Grey: gaps >0.6 s', fontsize=10)
        for ax, label in zip(axes[:5], ['Speed\n(km/h)', 'Throttle\n(%)', 'Brake\n(on / off)', 'Gear', 'RPM\n(rev/min)']):
            ax.set_ylabel(label)
        axes[1].set_ylim(-5, 105)
        axes[2].set_yticks([0, 1], ['off', 'on']); axes[2].set_ylim(-.15, 1.15)
        axes[3].set_yticks([2, 4, 6, 8])
        axes[5].plot(grid, base.mask_gaps(grid, delta, pair), color='#263446', lw=1.6, label='Sector-aligned delta estimate')
        axes[5].plot(grid, base.mask_gaps(grid, whole, pair), color='#987024', lw=1.1, ls='--', label='Whole-lap normalization sensitivity')
        axes[5].fill_between(grid, base.mask_gaps(grid, delta, pair), base.mask_gaps(grid, whole, pair), color='#987024', alpha=.10)
        axes[5].axhline(0, color='#a0a0a0', lw=.7)
        axes[5].scatter(anchors, official, color='#263446', marker='D', s=25, zorder=5)
        axes[5].set_ylabel('Estimated Δt (s)\nReference − fastest')
        axes[5].legend(loc='upper left', fontsize=8, frameon=False)
        for x, y, label in zip(anchors[1:], official[1:], ['S1', 'S2 cumulative', 'Finish']):
            axes[5].annotate(f'{label} {y:+.3f} s', (x, y), xytext=(-6, 10), textcoords='offset points', ha='right', fontsize=8)
        base.decorate(axes, pair, corners, 0, base.LENGTH, anchors)
        start_separation = abs((reference['lap'].LapStartTime - fastest['lap'].LapStartTime).total_seconds())
        w_fast, w_ref = fastest['lap'].get_weather_data(), reference['lap'].get_weather_data()
        if not all(d['lap'].Compound == 'SOFT' and d['lap'].FreshTyre and d['lap'].TyreLife == 2 for d in pair.values()):
            raise ValueError('Update figure tyre controls for the selected laps')
        fig.text(.09, .055,
                 f'Both: SOFT, fresh set, TyreLife 2 (includes out-lap) · Starts {start_separation:.3f} s apart · Track evolution uncontrolled.\n'
                 f'Weather snapshots (fastest / reference): air {w_fast.AirTemp:.1f}/{w_ref.AirTemp:.1f}°C; track {w_fast.TrackTemp:.1f}/{w_ref.TrackTemp:.1f}°C; '
                 f'wind {w_fast.WindSpeed:.1f}/{w_ref.WindSpeed:.1f} m/s. Fuel, traffic, damage and modes unknown.\n'
                 f'Positive delta: reference slower · Timing anchors enforced · Maximum alignment-method spread {spread:.3f} s (not a confidence interval).',
                 fontsize=10, linespacing=1.5)
        fig.savefig(base.OUT / f'{name}.png', dpi=180)
        fig.savefig(base.OUT / f'{name}.svg')
        plt.close(fig)
        metadata = ['Driver', 'LapNumber', 'LapTime', 'LapStartTime', 'LapStartDate', 'Compound', 'TyreLife', 'FreshTyre', 'IsAccurate', 'Deleted', 'TrackStatus', 'FastF1Generated']
        selection[drv] = {'fastest': base.plain(fastest['lap'][metadata].to_dict()),
                          'reference': base.plain(reference['lap'][metadata].to_dict()),
                          'chronological_runs': {role: d['run'] for role, d in pair.items()},
                          'quality': {role: base.plain(d['quality']) for role, d in pair.items()},
                          'weather': {role: base.plain(d['lap'].get_weather_data().to_dict()) for role, d in pair.items()},
                          'sector_delta_reference_minus_fastest_s': np.diff(official).tolist(),
                          'cumulative_delta_reference_minus_fastest_s': official.tolist(),
                          'lap_start_separation_s': start_separation,
                          'maximum_alignment_method_spread_s': spread,
                          'graph_png': f'{name}.png'}
        for role, d in pair.items():
            summary_rows.append({'Driver': drv, 'Role': role, 'ChronologicalRun': d['run'],
                                 'LapNumber': int(d['lap'].LapNumber), 'LapTime_s': d['duration'],
                                 'LapStartUTC': str(d['lap'].LapStartDate),
                                 'S1_s': np.diff(d['sector_t'])[0], 'S2_s': np.diff(d['sector_t'])[1], 'S3_s': np.diff(d['sector_t'])[2]})
        print(f'{drv}: fastest lap {int(fastest["lap"].LapNumber)} {time_label(fastest["duration"])}; '
              f'reference lap {int(reference["lap"].LapNumber)} {time_label(reference["duration"])}; gap {official[-1]:+.3f} s; '
              f'method spread {spread:.3f} s')
        print(f'  Original samples / long gaps: ' + '; '.join(f'{role} {d["quality"]["samples"]}/{d["quality"]["long_gap_count"]}' for role, d in pair.items()))
    audit = {'session': '2026 Singapore Grand Prix Qualifying Q3', 'fastf1_version': base.fastf1.__version__,
             'delta_sign': 'reference minus fastest; positive means reference slower',
             'sector_distance_anchors_m': anchors.tolist(), 'drivers': selection}
    (base.OUT / 'reference_laps_audit.json').write_text(json.dumps(audit, indent=2) + '\n')
    pd.DataFrame(summary_rows).to_csv(base.OUT / 'reference_laps_summary.csv', index=False)


if __name__ == '__main__':
    main()
