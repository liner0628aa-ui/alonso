"""Reproducible, offline SkillCorner smoke report. No downloads or event inference.

Run: .venv/bin/python -m src.analysis.spatial_engine_report
Raw acquisition commands and pinned hashes are in the generated validation report.
"""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
from time import perf_counter

import numpy as np
import pyarrow as pa

from src.data.sources.skillcorner_tracking import adapt_frames, parse_timestamp
from src.spatial.coordinates import PitchConfig, VERSION, ZONES
from src.spatial.features import DEFAULT_RADII, frame_features, window_features

COMMIT = '4340d274572876239c154c90bc507a9b3250a656'
BASE_URL = f'https://raw.githubusercontent.com/SkillCorner/opendata/{COMMIT}'
TRACKING_URL = (f'https://media.githubusercontent.com/media/SkillCorner/opendata/{COMMIT}'
                '/data/matches/1886347/1886347_tracking_extrapolated.jsonl')
RAW_HASHES = {
    '1886347_match.json': '30c608e78663e9f490b3545479a3ce67b171f418c5133d5609cb249a2466abb2',
    'tracking_prefix.jsonl': 'a9007d3e342b4d5acc18a7defea62cadaf7a9cd934ca64d8d1a39796b60e3cc9',
    'LICENSE': '3384cc66ffd008209759af5e6328677eabded72756fb1f56f4f82e68e9b3c6eb',
}
MIN_TEAM_PLAYERS = 3
VALID_DATA = 'Finite in-pitch x_m/y_m; visible=true; detected=true; canonical team and track identities'


def check_results(players, teams, player_windows, team_windows):
    """Reject physically impossible or internally inconsistent feature outputs."""
    checked = 0
    for table in (players, teams, player_windows, team_windows):
        for row in table.to_pylist():
            for key, value in row.items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    checked += 1
                    if not np.isfinite(value):
                        raise ValueError(f'Non-finite result: {key}')
                    if ('distance_m' in key or key.startswith(('local_', 'mean_local_'))) and value < 0:
                        raise ValueError(f'Negative spatial result: {key}')
                    if ('occupancy' in key or key.endswith('fraction')) and not 0 <= value <= 1:
                        raise ValueError(f'Invalid share: {key}')
                    if 'team_width_m' in key and not 0 <= value <= 68:
                        raise ValueError(f'Impossible width: {key}')
                    if 'team_depth_m' in key and not 0 <= value <= 105:
                        raise ValueError(f'Impossible depth: {key}')
    for row in player_windows.to_pylist():
        occupancies = [row[f'tracking_{zone}_occupancy'] for zone in ZONES]
        if row['observed_frames']:
            if any(v is None for v in occupancies) or not np.isclose(sum(occupancies), 1., atol=1e-10):
                raise ValueError('Occupancies must sum to one')
            if not np.isclose(row['tracking_halfspace_occupancy'], occupancies[1]+occupancies[3]):
                raise ValueError('Combined halfspace occupancy mismatch')
        elif any(v is not None for v in occupancies):
            raise ValueError('No observations must yield NULL occupancy')
        for key, value in row.items():
            if key.startswith('valid_') and value > row['observed_frames']:
                raise ValueError('Metric support exceeds observed frames')
        expected = row['expected_frames']
        if expected is not None and row['observed_frames'] > expected:
            raise ValueError('Player coverage exceeds expected frames')
    for row in team_windows.to_pylist():
        if not 0 <= row['valid_team_frames'] <= row['observed_frames'] <= row['expected_frames']:
            raise ValueError('Invalid team frame counts')
    return dict(status='PASS', finite_numeric_values_checked=checked,
                checks=['finite values', 'nonnegative distances and densities', 'pitch-bounded extents',
                        'occupancies sum to one', 'halfspace sum', 'coverage bounds'])


def feature_dictionary(tables, *, min_team_players=MIN_TEAM_PLAYERS, pitch=None):
    """Exact per-column definitions for every frame, window and coverage output."""
    pitch = pitch or PitchConfig()
    boundaries = [0., *(round(f*pitch.width_m, 10) for f in pitch.lane_fractions), pitch.width_m]
    identifiers = {
        'match_id': 'Namespaced source match identity', 'period': 'Source period integer; windows never mix periods',
        'frame_id': 'Source frame integer; unique per match and period at one timestamp',
        'timestamp_s': 'Numeric source match-clock seconds; retained independently of period',
        'team_id': 'Namespaced verified team identity', 'player_id': 'Namespaced provider player identity, NULL for anonymous tracks',
        'track_id': 'Namespaced trajectory identity scoped to source segment by adapter',
        'source': 'Source/method label; provider estimates are not independent ground truth',
        'coordinate_confidence': 'Provider confidence preserved as text on its native scale; NULL if unreported',
        'identity_confidence': 'Provider identity confidence preserved as text on its native scale; NULL if unreported',
        'attacking_direction': 'Explicit positive_x or negative_x per match/team/period in shared canonical frame',
        'visible': 'Provider visibility flag; SkillCorner uses is_detected as on-screen proxy; unknown=NULL',
        'detected': 'Provider detection flag; false includes extrapolations; unknown=NULL',
        'entity_id': 'player:<player_id> when known, otherwise track:<track_id>; grouping within match/period/team',
        'track_ids': 'Sorted pipe-separated track IDs contributing input rows to this entity/window',
        'window_start_s': 'Inclusive selected window start in source clock seconds',
        'window_end_s': 'Exclusive selected window end in source clock seconds',
        'sample_interval_s': 'Declared uniform sampling interval; off-grid and duplicate-slot frames rejected',
        'min_team_players': 'Configured minimum valid visible team-player count for extents',
    }
    rows = []
    for level, table in tables.items():
        for key in table.column_names:
            unit, aggregation, required = 'count', 'none', VALID_DATA
            missing = 'NULL when no valid observations contribute; never zero-filled'
            definition = None
            if key in identifiers:
                definition, unit, required = identifiers[key], 'identifier/metadata', 'Canonical rows or explicit window configuration'
                missing = 'Required except nullable player ID, confidence, visible and detected; unknown stays NULL'
            elif key in ('x_m', 'y_m', 'team_x_m', 'team_y_m'):
                axis = 'x' if 'x_m' in key else 'y'
                unit = 'm on canonical pitch'
                definition = (f'{axis} in shared 105x68 stadium frame; x right, y down' if not key.startswith('team_') else
                    f'Team-relative {axis}; negative_x attack rotates (x,y) to (105-x,68-y); y=0 attacking left')
            elif key == 'valid_observation':
                unit, definition, missing = 'boolean', 'visible=true AND detected=true AND complete finite coordinate pair inside closed pitch bounds', 'Always boolean; invalid rows retained'
            elif key == 'pitch_zone':
                unit = 'category'
                definition = '; '.join(f'{zone}: {boundaries[i]:g}<=team_y_m'+
                    ('<=' if i == 4 else '<')+f'{boundaries[i+1]:g}' for i, zone in enumerate(ZONES))
            elif key.startswith('tracking_avg_'):
                unit, aggregation = 'm on canonical pitch', 'Equal valid-frame arithmetic mean'
                definition = f"Mean team-relative {key[-3]} coordinate over observed_frames; requires explicit direction"
            elif key.startswith('tracking_') and key.endswith('_occupancy'):
                zone = key[len('tracking_'):-len('_occupancy')]
                unit, aggregation = 'share', 'Equal valid-frame share; regular-grid tracking-time representation'
                definition = ('tracking_left_halfspace_occupancy + tracking_right_halfspace_occupancy' if zone == 'halfspace'
                              else f'Number of valid player frames with pitch_zone={zone} / observed_frames')
            elif 'nearest_' in key and not key.startswith('valid_'):
                kind = 'teammate' if 'teammate' in key else 'opponent'
                unit = 'm on canonical pitch'
                definition = f'Minimum Euclidean distance to other valid visible {kind}; self excluded; shared coordinates'
                missing = f'NULL if target invalid or no valid visible {kind}; not infinity or zero'
                if key.startswith(('mean_', 'median_')):
                    aggregation = key.split('_')[0] + f' over valid_nearest_{kind}_frames'
                    definition = f'{aggregation} of per-frame nearest {kind} distance'
            elif (key.startswith('local_') or key.startswith('mean_local_')):
                radius = float(key.rsplit('_r', 1)[1])
                kind = 'teammates' if 'teammates' in key else 'opponents'
                definition = f'Count of other valid visible {kind} within Euclidean distance <= {radius:g}m + 1e-9m; self excluded'
                missing = f'NULL if target invalid or no valid visible {kind}; zero only with observed support outside radius'
                if key.startswith('mean_'):
                    aggregation = 'Arithmetic mean over valid_'+key[5:]+'_frames'
            elif key.startswith('valid_nearest_'):
                kind = key[len('valid_nearest_'):-len('_frames')]
                definition = f'Count of frames with non-NULL nearest_{kind}_distance_m; mean/median denominator'
                aggregation, missing = 'Count', 'Zero when no contributing frames'
            elif key.startswith('valid_local_'):
                definition = f'Count of frames with non-NULL {key[len("valid_"):-len("_frames")]}; corresponding mean denominator'
                aggregation, missing = 'Count', 'Zero when no contributing frames'
            elif 'team_width_m' in key or 'team_depth_m' in key:
                axis = 'y_m' if 'width' in key else 'x_m'
                unit = 'm on canonical pitch'
                definition = f'max({axis}) - min({axis}) over valid visible players in team/frame; requires >= {min_team_players} players; includes goalkeepers'
                missing = f'NULL below {min_team_players} valid visible players; no unseen-player imputation'
                if key.startswith(('mean_', 'median_')):
                    aggregation = key.split('_')[0] + ' of non-NULL frame extents'
            elif key in ('visible_team_players', 'mean_visible_team_players'):
                definition = 'Number of valid visible/detected in-pitch team players; includes goalkeepers; zero if team absent in an available frame'
                missing = 'Zero is an observed count, never an inferred tactical extent'
                if key.startswith('mean_'):
                    aggregation = 'Arithmetic mean over observed_frames; wholly absent frames excluded'
            elif key in ('valid_team_frames', 'valid_team_width_frames', 'valid_team_depth_frames'):
                definition = 'Count of frames with non-NULL '+('both width and depth' if key == 'valid_team_frames' else key[len('valid_'):-len('_frames')])
                aggregation, missing = 'Count', 'Zero when no contributing frames'
            elif key == 'observed_frames':
                definition = ('Valid visible/detected in-pitch player-frame count; denominator for position and occupancy' if level == 'player_window'
                              else 'Available team-frame rows; includes zero-visible-player rows; denominator for mean_visible_team_players')
                aggregation, missing = 'Count', 'Zero when no observations'
            elif key == 'expected_frames':
                definition = ('Explicit eligible player sampling-slot count supplied by caller for this window; roster needed; never inferred from detection' if level == 'player_window'
                              else '(window_end_s-window_start_s)/sample_interval_s; integer count of expected team sampling slots')
                missing = 'NULL if player eligibility unknown; team grid count always known'
            elif key == 'visible_fraction':
                unit = 'share'
                definition = ('observed_frames / expected_frames' if level == 'player_window' else 'visible_frames / expected_frames; at least one valid player, not full-team completeness')
                missing = 'NULL for unknown or zero expected_frames'
            elif key == 'frame_coverage_fraction':
                unit, definition, missing = 'share', 'observed_frames / expected_frames; available team-frame support, independent of visibility', 'NULL for zero expected_frames'
            elif key == 'visible_frames':
                definition, aggregation, missing = 'Count of team frames with visible_team_players > 0', 'Count', 'Zero when no visible support'
            elif key == 'time_span_s':
                unit, definition = 's', 'Last valid player timestamp minus first valid timestamp; not observed duration; zero for one observation'
            else:
                definitions = {
                    'input_rows': 'Count of input canonical rows, including invalid/missing observations',
                    'valid_player_observations': 'Count of valid visible/detected in-pitch players in frame',
                    'missing_coordinate_rows': 'Count of rows whose x_m and y_m are both NULL',
                    'out_of_pitch_rows': 'Count of finite rows outside closed pitch rectangle but within 0.1m tolerance; excluded, never clipped',
                    'nonvisible_or_unknown_rows': 'Count of rows with visible false or NULL',
                    'nondetected_or_unknown_rows': 'Count of rows with detected false or NULL',
                    'visible_teams': 'Number of distinct teams with at least one valid visible player in frame',
                }
                definition = definitions.get(key)
                aggregation, missing = 'Count', 'Zero when no qualifying rows'
            if definition is None:
                raise ValueError(f'Missing dictionary definition: {level}.{key}')
            rows.append(dict(feature=key, level=level, unit=unit, definition=definition,
                             required_data=required, aggregation=aggregation, missing_policy=missing,
                             tracking_or_event='tracking', version=VERSION))
    return rows


def write_csv(path, rows, columns=None):
    if isinstance(rows, pa.Table):
        columns, rows = rows.column_names, rows.to_pylist()
    with path.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=columns or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plot_frame(players, metadata, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle, Circle

    valid = [r for r in players.to_pylist() if r['valid_observation']]
    counts = Counter(r['frame_id'] for r in valid)
    fid = min(counts, key=lambda frame: (-counts[frame], frame))
    selected = [r for r in valid if r['frame_id'] == fid]
    fig, ax = plt.subplots(figsize=(11, 7))
    ax.add_patch(Rectangle((0, 0), 105, 68, fill=False, color='#334155'))
    ax.plot([52.5, 52.5], [0, 68], color='#94a3b8')
    ax.add_patch(Circle((52.5, 34), 9.15, fill=False, color='#94a3b8'))
    roster = {f"skillcorner:player:{p['id']}": p for p in metadata['players']}
    for side, color in [('home', '#2563eb'), ('away', '#ea580c')]:
        team = metadata[side+'_team']
        rs = [r for r in selected if r['team_id'] == f"skillcorner:team:{team['id']}"]
        ax.scatter([r['x_m'] for r in rs], [r['y_m'] for r in rs], color=color, s=45, label=team['name'])
        for r in rs:
            ax.annotate(f"#{roster[r['player_id']]['number']} ({r['player_id'].split(':')[-1]})",
                        (r['x_m'], r['y_m']), xytext=(4, 5), textcoords='offset points', fontsize=7)
    ax.set(xlim=(-2, 107), ylim=(70, -2), aspect='equal', xlabel='Shared canonical x (m)', ylabel='Shared canonical y (m)',
           title=f"SkillCorner match 1886347 | period 1 | {selected[0]['timestamp_s']:.1f}s | frame {fid}\n"
                 'Detected-visible players only; labels: jersey (provider player ID)')
    ax.legend(loc='upper center', bbox_to_anchor=(.5, -.1), ncol=2)
    fig.text(.02, .015, 'Data: SkillCorner Open Data (MIT). Broadcast estimates; unseen players omitted. Home attacks ←, away →.', fontsize=8)
    fig.tight_layout(rect=(0, .04, 1, 1))
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return fid


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-dir', type=Path, default=Path('data/raw/spatial_skillcorner'))
    parser.add_argument('--output-dir', type=Path, default=Path('outputs/spatial_feature_engine_v1'))
    args = parser.parse_args(argv)
    raw, out = args.raw_dir, args.output_dir
    for name, expected in RAW_HASHES.items():
        if not (raw/name).is_file() or hashlib.sha256((raw/name).read_bytes()).hexdigest() != expected:
            raise ValueError(f'Missing or changed pinned source file: {raw/name}; see reproduction instructions')
    metadata = json.loads((raw/'1886347_match.json').read_text())
    # Byte-range download ends mid-record. Drop only the unfinished final record.
    prefix = (raw/'tracking_prefix.jsonl').read_bytes()
    lines = prefix.splitlines() if prefix.endswith(b'\n') else prefix.splitlines()[:-1]
    frames = [json.loads(line) for line in lines]
    frames = [f for f in frames if f['period'] == 1 and f['timestamp'] is not None
              and 0 <= parse_timestamp(f['timestamp']) < 30]
    if [f['frame'] for f in frames] != list(range(10, 310)):
        raise ValueError('Pinned smoke slice must contain exactly frames 10..309')
    started = perf_counter()
    canonical = adapt_frames(frames, metadata)
    players, teams, quality = frame_features(canonical, min_team_players=MIN_TEAM_PLAYERS)
    # Explicit roster eligibility: all selected sampling slots fall within these by-period intervals.
    expected = {}
    for p in metadata['players']:
        intervals = p['playing_time']['by_period']
        eligible = sum(any(i['name'] == 'period_1' and i['start_frame'] <= f['frame'] < i['end_frame']
                           for i in intervals) for f in frames)
        if eligible:
            expected[(f"skillcorner:match:{metadata['id']}", 1, f"skillcorner:team:{p['team_id']}",
                      f"player:skillcorner:player:{p['id']}")] = eligible
    pw, tw = window_features(players, teams, start_s=0, end_s=30, sample_interval_s=.1, expected_frames=expected)
    runtime = perf_counter()-started
    sanity = check_results(players, teams, pw, tw)
    out.mkdir(parents=True, exist_ok=True)
    tables = dict(player_frame=players, team_frame=teams, frame_quality=quality, player_window=pw, team_window=tw)
    write_csv(out/'player_spatial_features.csv', pw)
    write_csv(out/'team_spatial_features.csv', tw)
    write_csv(out/'frame_quality_summary.csv', quality)
    write_csv(out/'team_frame_features.csv', teams)
    write_csv(out/'feature_dictionary.csv', feature_dictionary(tables))
    selected_frame = plot_frame(players, metadata, out/'sample_tracking_frame.png')
    rows = canonical.to_pylist()
    valid_counts = [r['valid_player_observations'] for r in quality.to_pylist()]
    manifest = dict(version=VERSION, source='SkillCorner Open Data', commit=COMMIT,
        tracking_url=TRACKING_URL, metadata_url=f'{BASE_URL}/data/matches/1886347/1886347_match.json',
        license_url=f'{BASE_URL}/LICENSE', documentation_url=f'{BASE_URL}/README.md',
        coordinate_diagram_url=f'{BASE_URL}/assets/field.jpg', raw_sha256=RAW_HASHES,
        raw_bytes=1048576, match_id=1886347, period=1, time_range_s=[0., 30.], interval='[start,end)',
        first_frame=10, last_frame=309, frames=len(frames), teams=len({r['team_id'] for r in rows}),
        tracked_identities=len({r['track_id'] for r in rows}), input_rows=len(rows),
        valid_observations=sum(valid_counts), provider_pitch_m=[metadata['pitch_length'], metadata['pitch_width']],
        canonical_pitch_m=[105, 68], conversion='x_m=(x/104+0.5)*105; y_m=(0.5-y/68)*68; team-relative rotation if negative_x',
        shared_coordinate_ranges={k: [min(r[k] for r in rows if r[k] is not None), max(r[k] for r in rows if r[k] is not None)] for k in ('x_m','y_m')},
        visible_player_distribution=dict(sorted(Counter(valid_counts).items())),
        min_team_players=MIN_TEAM_PLAYERS, radii_m=DEFAULT_RADII, lane_fractions=PitchConfig().lane_fractions,
        sample_interval_s=.1, plotted_frame=selected_frame, engine_runtime_s=runtime, sanity=sanity)
    (out/'source_manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    (out/'SKILLCORNER_LICENSE.txt').write_bytes((raw/'LICENSE').read_bytes())
    write_validation(out, manifest, pw, tw)
    print(json.dumps(manifest, indent=2))


def write_validation(out, manifest, pw, tw):
    report = f'''# Spatial Feature Engine v1 — validation report

## Result and real sample

PASS: deterministic canonical tracking → player/frame/window and team/frame/window features.
The source is [SkillCorner Open Data]({BASE_URL}/README.md), pinned to `{COMMIT}`.
Published repository [MIT license]({BASE_URL}/LICENSE) inspected before use; attribution: SkillCorner.
The full notice is retained in SKILLCORNER_LICENSE.txt. No footage was downloaded or processed.
These are provider broadcast estimates, **not independently established tracking ground truth**.
The exact synthetic geometry tests provide the reference answers; the real slice tests integration.

- Match 1886347: Auckland FC vs Newcastle United Jets FC, 2024-11-30.
- File: `data/matches/1886347/1886347_tracking_extrapolated.jsonl`.
- Slice: period 1, source match-clock `[0.0,30.0)` seconds, frame IDs 10–309 inclusive, 300 frames at 10Hz.
- Raw acquisition: only bytes 0–1048575 (1 MiB); incomplete last JSONL line ignored, pre-match empty/unclocked frames excluded explicitly.
- {manifest['teams']} teams; {manifest['tracked_identities']} tracked identities; {manifest['input_rows']} input player rows.
- {manifest['valid_observations']} valid detected-visible positions; all other rows retained with NULL features.
- Shared canonical coordinate min/max, including extrapolated input positions: {manifest['shared_coordinate_ranges']}.
- Per-frame valid-visible player distribution (count: number of frames): {manifest['visible_player_distribution']}.
- Core runtime: {manifest['engine_runtime_s']:.6f} seconds (adapter, validation, frame and window computation; excludes I/O, plotting and source downloads).
- Sanity checks: **{manifest['sanity']['status']}**, {manifest['sanity']['finite_numeric_values_checked']} finite numeric values checked; nonnegative distances/counts, pitch-bounded width/depth, occupancy sums and coverage denominators verified.
- 0 tolerated out-of-pitch rows in this slice; 0 gross-coordinate failures. No clipping or zero imputation.
- {pw.num_rows} player-window rows and {tw.num_rows} team-window rows; plot uses frame {manifest['plotted_frame']}.

## Canonical schema and geometry

Arrow typed columns: match_id, period, timestamp_s, frame_id, team_id, nullable player_id,
required track_id, x_m, y_m, nullable visible/detected, source, nullable confidence strings,
and required attacking_direction. x_m/y_m implement the logical x/y fields in canonical metres.
Confidence strings preserve native scales/categories, without implying comparable probabilities.
The full Step 2 proposed research/event schema remains untouched; this is its deliberately minimal tracking subset.

Canonical pitch: 105×68m, shared stadium x increasing right and y increasing down.
Team-relative coordinates have x=0 own goal, x=105 opponent goal, y=0 attacking left.
For negative-x attacks **both axes rotate**: (105-x,68-y). This is a 180° rotation,
preserving handedness; x-only reflection would swap left/right tactical lanes incorrectly.
All neighbour distances use the shared frame before either team's rotation.

The provider [diagram]({BASE_URL}/assets/field.jpg) shows centred metre coordinates,
positive x right, positive y up. [Match metadata]({BASE_URL}/data/matches/1886347/1886347_match.json)
gives 104×68m and home_team_side=[right_to_left,left_to_right]. The adapter uses that
metadata, never the player arrangement, to assign directions; away directions are opposite.
Conversion: x_m=(x/104+0.5)*105, y_m=(0.5-y/68)*68.
Longitudinal standardization stretches x distances by 105/104 (about 0.96%); reported
Euclidean metres are on the canonical pitch, not exact surveyed-ground distances on this 104m pitch.

The canonical validator rejects nonnumeric clocks, nonfinite/incomplete coordinate pairs,
missing track IDs, duplicate track/player frames, conflicting identities/directions and clocks.
NULL coordinate pairs remain NULL. Out-of-bounds beyond 0.1m fails loudly; smaller
overshoots are flagged and excluded from features without clipping. Unknown visibility or
detection is excluded conservatively. Source detection is represented by `is_detected`;
the adapter maps it to detected and to the explicitly disclosed on-screen visibility proxy.

## Features and coverage

The project's explicit v1 lateral convention is left_wide [0,13.6), left_halfspace [13.6,27.2),
central [27.2,40.8), right_halfspace [40.8,54.4), right_wide [54.4,68]. This is not a universal
industry definition. Boundaries live in PitchConfig; radii are configurable and default to 5m/10m.
Inclusive radius comparisons use a 1e-9m numerical tolerance. Self is excluded.
No visible valid neighbour of a category means NULL distance **and count**; zero count means
at least one neighbour was observed but none was inside that radius.

Player windows use equal valid-frame means/shares on an explicit uniform 0.1s grid.
This is a tracking-frame/time representation, not event weighting. Off-grid or repeated sampling
slots fail; gaps are never interpolated or weighted as observed time. time_span_s is last minus
first valid timestamp, not observed duration. Windows are half-open and never mix periods.
Known player IDs group track segments; anonymous tracks remain separate. Identity switches
must be corrected or explicitly split by the provider adapter, never guessed in the engine.

Player observed_frames is the denominator for all position/occupancy features. Each neighbour
distance and density aggregate has its own valid-frame count. expected_frames is provided only
from explicit roster eligibility: metadata playing_time.by_period intervals contain all 300 selected
frames for each of the 22 participants. visible_fraction=observed_frames/expected_frames measures
usable positional visibility, not confidence. Unknown eligibility leaves that fraction NULL.

Width=max(y)-min(y), depth=max(x)-min(x), including goalkeepers, only with at least 3 valid
visible team players. These are **observed-subset extents**, not inferred full-team dimensions.
Team windows expose separate valid width/depth counts and valid_team_frames. Their
mean_visible_team_players averages available frames (including zero-visible team rows);
wholly absent source frames do not become zero-player frames. frame_coverage_fraction measures
input-frame availability; visible_fraction measures sampling slots with at least one valid visible
team player. Neither means all 11 players were seen. Source rows absent for an entire frame
cannot be reconstructed from player records; expected grid counts still expose that gap.

## Verification

Run `.venv/bin/python -m pytest -q` for the existing suite and focused spatial/adapter/report tests.
Exact fixture: A1=(50,34), A2=(53,38), A3=(40,10), B1=(55,34), B2=(70,50).
A1 nearest teammate=5m; nearest opponent=5m; teammate/opponent counts at 5m and 10m each=1.
A2 nearest opponent=sqrt(20)m; A3 nearest teammate=26m. Team A width=28m and depth=13m;
Team B width=16m and depth=15m when explicitly lowering minimum players to 2 for that fixture.
Paired mirrored scenes preserve team-relative coordinates, zones, distances and extents.
Tests also cover missing coordinates/opponents, duplicates, nonfinite/out-of-pitch values,
empty input, anonymous tracks, one-player teams, partial visibility, window gaps and support counts.
Sanity-guard tests deliberately inject negative distances, oversized extents, nonfinite means,
invalid occupancy sums and coverage >1 and verify rejection.
Final suite results and protected-file hash checks are recorded in verification.json.

## Reproduce without committing raw data

From repository root (network access needed only for these three pinned downloads):

```bash
mkdir -p data/raw/spatial_skillcorner
curl -L --fail --range 0-1048575 '{TRACKING_URL}' -o data/raw/spatial_skillcorner/tracking_prefix.jsonl
curl -L --fail '{BASE_URL}/data/matches/1886347/1886347_match.json' -o data/raw/spatial_skillcorner/1886347_match.json
curl -L --fail '{BASE_URL}/LICENSE' -o data/raw/spatial_skillcorner/LICENSE
.venv/bin/python -m src.analysis.spatial_engine_report
```

The report command checks raw SHA256 values before computation; hashes and URLs are in
source_manifest.json. data/raw is already git-ignored. No new dependencies are needed.
CSV content is deterministic for the pinned slice and configuration; runtime metadata varies.
The core entry points are canonical_table, frame_features and window_features in src/spatial.
Player-frame tables are returned by the engine; window CSVs, team-frame CSV and quality CSV
are saved for inspection. Every returned/exported column is covered by feature_dictionary.csv.

## Research limitations and stop condition

- Tracking position ≠ event position; see event_tracking_compatibility.md. Rescaling does not fix sampling bias.
- Future broadcast tracking may have severe visibility and identity bias. This source already demonstrates incomplete observation.
- Width/depth are biased when off-screen players are missing; a small observed extent is not evidence of tactical compactness.
- Nearest visible distance can exceed true nearest distance; observed local density can undercount the true density.
- No possession state, pass, carry, reception, pressure, shot, assist or other event is inferred or used.
- No tactical instruction or coach causality is inferred. No Alonso-specific result is produced.
- Spatial thresholds/zones are explicit project conventions. Confidence is unreported, not perfect.
- One 30-second sample establishes reproducible computation, not match representativeness or provider accuracy.
- No CV, video, model fitting, clustering, formation or between-line inference is implemented.

STOP: deterministic tracking → spatial features only. Next minimum action is review of these
definitions and coverage before selecting a larger rights-cleared tracking validation sample.
'''
    (out/'validation_report.md').write_text(report)


if __name__ == '__main__':
    main()
