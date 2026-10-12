# Singapore Q3 telemetry comparison

Four graphs for engineering assessment practice, generated from FastF1 3.8.3 public broadcast data for **Grand Prix qualifying on 10 October 2026**, rather than Sprint Qualifying.

- [Full-lap comparison](outputs/01_full_lap.png): speed, throttle, brake state, gear, RPM and estimated cumulative time delta for both drivers, with approximate turn markers.
- [Turn 7 detail](outputs/02_turn7_detail.png): the same channels, with braking-entry intervals, speed-minimum apex proxies and throttle-recovery exit proxies.

- [Verstappen: fastest vs reference Q3 lap](outputs/03_ver_reference.png): lap 11 (first run, 1:31.373) against lap 14 (final run, 1:31.625).
- [Leclerc: fastest vs reference Q3 lap](outputs/04_lec_reference.png): lap 24 (final run, 1:31.427) against lap 21 (first run, 1:31.661).

All figures also have SVG versions in `outputs/` for clear zooming or printing. Blue is Verstappen; red is Leclerc. These are constructed practice materials, not McLaren assessment questions.

## 1. Select comparable laps

[Official Formula 1 results](https://www.formula1.com/en/results/2026/races/1296/singapore/qualifying) identify these as the two fastest Q3 laps:

| Driver | FastF1 lap number | Lap time | Lap start, Singapore time (UTC+8) | Tyres |
| --- | --- | --- | --- | --- |
| Max Verstappen | 11 | 1:31.373 | 22:19:02.180 | SOFT, FreshTyre=True, TyreLife=2 |
| Charles Leclerc | 24 | 1:31.427 | 22:28:52.517 | SOFT, FreshTyre=True, TyreLife=2 |

Both are non-deleted, non-generated, non-pit laps, with `IsAccurate=True` and TrackStatus `1` (clear). IsAccurate concerns timing consistency; it does not certify telemetry accuracy. TyreLife is the reported number of laps on the set, including the out-lap; it is not two previous flying laps or a measured wear percentage. Equal compound and reported age do not establish equal tyre condition.

**The starts are 590.337 seconds apart.** These are best-lap comparisons, not fully controlled experiments. A useful check is the corresponding Q3 runs:

| Q3 run | VER | LEC | LEC minus VER |
| --- | --- | --- | --- |
| First | Lap 11, 1:31.373 | Lap 21, 1:31.661 | +0.288 s |
| Final | Lap 14, 1:31.625 | Lap 24, 1:31.427 | −0.198 s |

The apparent advantage reverses. This does not prove track evolution caused the change: driver execution, preparation and car behaviour also changed or remain unknown. Compare all four laps before attributing the selected pair's differences to technique.

## Additional reference laps: compare each driver with themselves

The two additional graphs compare each driver's fastest Q3 lap with their **second-fastest valid Q3 flying lap**. Each driver completed two valid Q3 flying laps, so these cover the first and final runs. Chronological order and performance rank are labelled separately: VER's fastest was his first run; LEC's fastest was his final run.

| Driver | Fastest Q3 lap | Second-fastest reference | Reference minus fastest | Sector differences S1 / S2 / S3 |
| --- | --- | --- | --- | --- |
| VER | Lap 11, 1:31.373 | Lap 14, 1:31.625 | +0.252 s | +0.031 / +0.111 / +0.110 s |
| LEC | Lap 24, 1:31.427 | Lap 21, 1:31.661 | +0.234 s | +0.003 / +0.167 / +0.064 s |

The coloured solid line is the fastest lap; the ochre dashed line is the reference. Each graph includes speed, throttle, Boolean brake state, gear, RPM and cumulative `t_reference − t_fastest` delta. Positive delta means the reference took longer to reach that derived location. These graphs use the same VER-fastest reference sector coordinates and approximate turn markers as the original comparisons. No braking or apex events are forced to align.

All four laps pass the timing/validity and broad sample-plausibility checks. The additional reference data contain 343 original car samples and two intervals over 0.6 s for VER, and 344 samples and four such intervals for LEC. There are no null channel values, duplicate/non-increasing timestamps or out-of-range values in these reference streams. Temporal gaps still represent missing evidence.

Within each driver, compound, reported freshness and age match: SOFT, FreshTyre=True, TyreLife=2. The laps came from different stints/sets. VER's starts are 634.256 s apart and LEC's 579.780 s apart. Weather snapshots, tyre preparation and track evolution can still differ; fuel, actual tyre condition, traffic effects, damage, setup adjustments and energy/active-aero modes remain unknown. Comparing the same driver/car reduces some confounding, but does not isolate technique or establish a controlled experiment.

The alignment-method spread is up to 0.113 s for VER and 0.090 s for LEC. As before, this is sensitivity rather than a confidence interval, and the exact timing anchors are enforced. Use the sector differences above for firm timing conclusions; use the local traces to identify hypotheses that require corroboration.

Run `.venv/bin/python reference_q3.py` to reproduce these two graphs. `reference_laps_audit.json` records each lap's metadata, quality checks, weather, chronological role, sector differences and method spread. `reference_laps_summary.csv` gives the selected laps and sector times; `VER_reference_delta.csv` and `LEC_reference_delta.csv` give derived delta estimates. The separate `VER_lap11_*`, `VER_lap14_*`, `LEC_lap21_*` and `LEC_lap24_*` exports retain original and derived channels without replacing the original fastest-lap comparison exports.

## 2. Inspect samples and units

| Check | VER | LEC |
| --- | --- | --- |
| Original car-stream samples | 347 | 341 |
| Null values / duplicate timestamps / non-increasing timestamps | 0 / 0 / 0 | 0 / 0 / 0 |
| Median sample interval | 0.240 s | 0.240 s |
| Maximum sample interval | 1.160 s | 1.240 s |
| Intervals longer than 0.6 s | 3 | 3 |
| Speed range | 63–308 km/h | 63–308 km/h |
| Throttle range | 0–100% | 0–100% |

No values failed the script's broad plausibility checks. That does not rule out erroneous but plausible values, timing offsets or unrecorded events. Missing rows appear as temporal gaps rather than NaNs. The 0.6-second threshold is a display/quality rule, not a physical confidence bound. Smaller gaps still limit resolution.

Speed is km/h; elapsed time is seconds; derived distance is metres; RPM is rev/min; throttle is a reported percentage; gear is a discrete integer. **Brake is Boolean on/off, not brake pressure, pedal force or percentage.** Position X/Y/Z uses feed coordinates in tenths of a metre; they are used only to locate approximate track markers. The legacy DRS channel is zero throughout both laps; this does not establish the 2026 active-aero state or energy deployment.

## 3. Separate original and derived data; synchronise

`Lap.get_car_data()` supplies the original car-stream timestamps and channels, with Source=`car` for every selected sample. “Original” here means the public stream delivered through FastF1, not access to the cars' engineering sensors. Dots retain these samples. Continuous-channel line segments imply linear interpolation for display; brake and gear use held steps. Lines break at intervals longer than 0.6 seconds.

The script avoids using merged `get_telemetry()` car/position data as if every channel were originally observed. Position data remains separate. It adds only interpolated start/finish speed boundaries using observed samples bracketing the timing line. It converts km/h to m/s and integrates speed with the trapezoidal rule. Timing-sector knots are inserted explicitly by interpolation. Derived distances, boundary speeds, marker locations and time deltas are not raw measurements.

The integrated full-lap distances are 4,881.23 m (VER) and 4,897.86 m (LEC), compared with the nominal 4,927 m track length. Differences can reflect sampling/integration error and different driven lines. The script therefore maps both drivers' three timing-sector distances to common sector boundaries defined by the VER reference, scaled to nominal lap length. It preserves each driver's own lap-relative timestamps and does not align braking, throttle or speed-minimum events.

This is **approximate spatial alignment**, not proof of matching geometric positions. Within-sector distances are scaled uniformly, and sector-boundary positions themselves are derived. Turn markers are manually supplied MultiViewer markers matched to the closest original VER position sample; they are approximate and do not measure the apex.

## 4. Plot distance, mark phases and estimate delta

The delta is `t_LEC(s) − t_VER(s)` obtained by linear interpolation of elapsed time onto a common 5 m display grid, with sector boundaries included. Positive means Leclerc has taken longer to reach that derived location. The grid does not create 5 m measurement resolution. Diamonds represent actual timing anchors, which the method enforces.

| Timing sector | VER | LEC | Sector difference | Cumulative difference |
| --- | --- | --- | --- | --- |
| S1 | 27.002 s | 27.025 s | +0.023 s | +0.023 s |
| S2 | 38.531 s | 38.401 s | −0.130 s | −0.107 s |
| S3 | 25.840 s | 26.001 s | +0.161 s | +0.054 s |

The dashed curve uses whole-lap distance normalization instead. Both methods enforce the finish gap, so finish agreement is not independent validation. Their maximum local disagreement is **0.193 s**. Shading between them is method sensitivity, not a confidence interval; shared errors can exceed that spread. Delta curves are hidden within long sample gaps, although integrating across missing speed intervals can still affect later distances. Do not quote precise corner gains from these curves. The official sector and lap differences are stronger evidence.

At Turn 7 the marked phases are operational proxies:

| Proxy | VER | LEC |
| --- | --- | --- |
| E: brake-on bracket, last off to first on | 1,608–1,693 m | 1,674–1,710 m |
| A*: lowest observed speed within the T7 window | 118 km/h, gear 3 | 123 km/h, gear 2 |
| X: first ≥95% throttle sample sustained for ≥0.5 s | ≈1,842 m | ≈1,854 m |

The entry brackets overlap, and VER's bracket spans **1.08 seconds without a sample**. These data cannot establish who braked later. A* is a sampled speed minimum, not a geometric apex, and X is throttle recovery, not a surveyed corner exit. Locations are rounded because the coordinate itself is uncertain. Neither true minimum speed nor exact full-throttle onset is guaranteed to coincide with a sample.

## 5. Controls and unknowns

| Control | Evidence and limitation |
| --- | --- |
| Compound / age | Same soft compound, reported fresh set, TyreLife=2. Actual wear, construction/set variation, pressure, surface/carcass temperature and preparation unknown. |
| Fuel | Unknown. Qualifying does not establish equal fuel mass. |
| Weather | Selected once-per-minute observations: air 29.7°C for both; track 39.6/39.8°C; rain False/False; wind 1.9/2.2 m/s at 165°/153°; humidity 73.8/74.5%; pressure 1010.5/1010.6 mbar (VER/LEC). Corner-level gusts and local grip unknown. |
| Traffic | Clear track-status flags and no Q3 impeding message specific to these two laps found. This does not rule out a tow, wake or obstruction. Car-to-car spacing and video verification remain outstanding. |
| Track evolution | Different Q3 runs, nearly ten minutes apart. Grip evolution and local surface condition unknown and uncontrolled. |
| Damage / mechanical state | No engineering damage verification. Leclerc publicly reported pulling under braking in Q1/Q2; this is context, not proof of the same issue on this Q3 lap. |
| Energy / aero modes | Battery state, electrical deployment, harvesting, active-aero state, power-unit maps and mode changes unknown. Legacy DRS=0 does not resolve them. |
| Car / setup | Different cars, gearing and setups. Brake balance, differential, aero balance, ride height and tyre condition unknown. Public channels cannot isolate driver contribution. |

Weather values are snapshots, not continuous controls. [Leclerc's post-session account](https://www.formula1.com/en/latest/article/i-had-a-lot-of-struggles-leclerc-reveals-misjudgement-that-cost-him-singapore-pole.10ZX0dKhEvCzFcqEfu3M0m.10ZX0dKhEvCzFcqEfu3M0m) also mentions wind-related misjudgement, but does not localise it to Turn 7.

## 6. Form hypotheses; seek evidence that separates explanations

| Observation | Testable hypothesis | Counterargument / alternative | Discriminating evidence |
| --- | --- | --- | --- |
| LEC's sampled T7 minimum is 5 km/h higher | He carried more speed through the corner. | A different line, spatial alignment or missed true minimum could account for it. Higher minimum alone does not establish a faster corner. | Time-synchronised onboard video; better position, steering, yaw rate and lateral acceleration; local elapsed time between fixed physical locations. |
| VER's full-throttle proxy is upstream of LEC's | VER prioritised earlier acceleration after a lower minimum. | Throttle is an input, not delivered wheel torque. Gearing, tyre state, electrical deployment and sampling differ. | Wheel speeds/slip, longitudinal acceleration, delivered torque and energy data; corroborating video; repetition on both Q3 runs. |
| LEC uses gear 2 around the minimum; VER gear 3 | Different gearing/rotation/traction strategies contributed. | Gear numbers alone do not specify ratios or wheel torque. Gear choice cannot prove oversteer, understeer or a traction problem. | Gear ratios, differential maps, steering/yaw response, wheel slip and driver feedback. |
| LEC gains 0.130 s in S2 but loses 0.161 s in S3 | A sector-dependent compromise or execution difference exists. | Multiple corners contribute; run timing, weather and car modes could also explain it. | Compare matched first/final runs, onboard mistakes and speed traps; inspect tyre/energy histories; seek repeatability. |
| LEC's brake signal ends later around T7 | Different brake release may affect rotation. | Brake state provides no pressure, balance, deceleration demand or steering measurement. It does not demonstrate trail-braking skill or brake malfunction. | Brake pressure/balance, steering, yaw rate, wheel lock/slip and higher-rate samples. |

For practice: choose one observation, describe the source and its resolution, propose two competing explanations, and name the measurement that would distinguish them. State what would falsify your preferred explanation. Keep “observed”, “estimated” and “hypothesised” separate.

## Reproduce and inspect

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python singapore_q3.py
.venv/bin/python reference_q3.py
```

The first run downloads public data; later runs reuse `.cache/`. The locally generated session pickle is for this project only. Do not replace it with an untrusted pickle.

`outputs/audit.json` records the quality checks, lap metadata, weather, phase proxies and alignment spread. `*_car_original.csv` and `*_position_original.csv` retain the selected source streams; `*_derived.csv` contains added coordinates. `q3_candidates.csv` preserves the candidate laps, `delta_estimates.csv` identifies interpolated values inside long gaps, and the official-sector, weather and race-control exports support the notes. The script checks selected times against official results and confirms the delta reproduces timing anchors; this checks the calculation, not physical spatial accuracy. Both figures were visually inspected.

Technical provenance: [FastF1 telemetry source and integration implementation](https://github.com/theOehrly/Fast-F1/blob/main/fastf1/core.py), [public-channel units](https://github.com/theOehrly/Fast-F1/blob/main/fastf1/_api.py), and [MultiViewer marker limitations](https://github.com/theOehrly/Fast-F1/blob/main/fastf1/mvapi/data.py). The actual run uses the pinned installed version listed above.
