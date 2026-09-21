"""Reusable canonical integrity checks and descriptive data-quality reports."""
from collections import Counter
from dataclasses import fields
from datetime import date
import math
from src.data.schema import NormalizedEvent, PlayerMatch
from src.data.coordinate_normalization import normalize_coordinates
from src.data.sources.aggregate_csv import RAW_STAT_COLUMNS

EVENT_TYPES={'PASS','CARRY','SHOT','DRIBBLE','RECEIPT','PRESSURE','TACKLE','INTERCEPTION','RECOVERY','FOUL','OTHER'}


def _unique(rows, keys):
    seen=set()
    for row in rows:
        key=tuple(row[k] for k in keys)
        if any(v is None or v=='' for v in key) or key in seen:
            raise ValueError(f'Null/duplicate key: {keys} {key}')
        seen.add(key)


def validate_dataset(data):
    matches,players,events,aggregates=(data[k] for k in ('matches','players','events','player_match_aggregate_stats'))
    _unique(matches,('match_id',)); _unique(matches,('data_source','source_match_id'))
    _unique(players,('match_id','player_id'))
    _unique(events,('event_id',)); _unique(events,('data_source','source_match_id','source_event_id'))
    _unique(aggregates,('data_source','source_match_id','player_id'))
    lookup={r['match_id']:r for r in matches}
    membership={(r['match_id'],r['player_id']):r['team_id'] for r in players}
    player_fields={f.name for f in fields(PlayerMatch)}
    for match in matches:
        date.fromisoformat(match['match_date'])
        for key in ('data_source','source_match_id','competition','season','home_team_id','away_team_id','home_team_name','away_team_name'):
            if not isinstance(match[key],str) or not match[key]: raise ValueError('Missing match metadata')
        if match['home_team_id']==match['away_team_id']: raise ValueError('Identical match teams')
        for side in ('home','away'):
            value=match[side+'_score']
            if value is not None and (type(value) is not int or value<0): raise ValueError('Invalid score')
    for row in players+aggregates:
        p=PlayerMatch(**{k:v for k,v in row.items() if k in player_fields}); p.validate()
        match=lookup.get(row['match_id'])
        if match is None: raise ValueError('Player without match')
        side=row['home_away']; other='away' if side=='home' else 'home'
        if row['team_id']!=match[side+'_team_id'] or row['opponent_id']!=match[other+'_team_id']:
            raise ValueError('Player-team match inconsistency')
        for key in ('data_source','source_match_id','competition','season','match_date'):
            if row[key]!=match[key]: raise ValueError('Player-match metadata conflict')
    for row in aggregates:
        if (row['match_id'],row['player_id']) not in membership: raise ValueError('Aggregate without player metadata')
        if row['event_data_available'] or row['spatial_data_available']: raise ValueError('Aggregate-only coverage flags')
        p=PlayerMatch(**{k:v for k,v in row.items() if k in player_fields})
        for name in RAW_STAT_COLUMNS:
            value=row[name]
            if value is not None:
                if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:
                    raise ValueError('Invalid raw aggregate')
                if name in p.features: p.set_feature(name,value,'observed','validation:source_raw')
                elif int(value)!=value: raise ValueError('Invalid count')
    event_fields={f.name for f in fields(NormalizedEvent)}
    indices={}
    for row in events:
        NormalizedEvent(**{k:v for k,v in row.items() if k in event_fields}).validate()
        if row['event_type'] not in EVENT_TYPES: raise ValueError('Unknown canonical taxonomy')
        match=lookup.get(row['match_id'])
        if match is None: raise ValueError('Event without match')
        if row['data_source']!=match['data_source'] or row['source_match_id']!=match['source_match_id']:
            raise ValueError('Event-match source mismatch')
        if row['team_id'] is not None and row['team_id'] not in (match['home_team_id'],match['away_team_id']):
            raise ValueError('Event team not in match')
        if row['player_id'] is not None and ((row['match_id'],row['player_id']) not in membership or membership[(row['match_id'],row['player_id'])]!=row['team_id']):
            raise ValueError('Event player/team absent from lineup')
        if row['event_type']!='OTHER' and row['player_id'] is None: raise ValueError('Player action without player')
        index=row['event_index']; previous=indices.get(row['match_id'])
        if previous is not None and (index<=previous[0] or row['period']<previous[1]): raise ValueError('Event order/duplicate index')
        indices[row['match_id']]=(index,row['period'])
        if row.get('timestamp') is not None and row['period'] in (1,2,3,4):
            parts=row['timestamp'].split(':')
            if len(parts)!=3: raise ValueError('Invalid period timestamp')
            hour,minute,second=map(float,parts)
            if hour<0 or not 0<=minute<60 or not 0<=second<60:
                raise ValueError('Invalid period timestamp range')
            elapsed=hour*3600+minute*60+second
            base={1:0,2:45,3:90,4:105}[row['period']]
            if row['minute']!=base+int(elapsed//60) or row['second']!=int(second):
                raise ValueError('Nominal minute/second contradict period timestamp')
        if row['data_source']=='statsbomb':
            expected=normalize_coordinates(row['source_x'],row['source_y'],row['source_end_x'],row['source_end_y'],width=120,height=80)
            for key,value in expected.items():
                if row[key]!=value: raise ValueError('Coordinate transform mismatch')
    return True


def quality_report(data, targets=None):
    events=data['events']; total=len(events)
    def missing(key): return 100*sum(r[key] is None for r in events)/total if total else None
    ranges={k:([min(v),max(v)] if (v:=[r[k] for r in events if r[k] is not None]) else [None,None])
            for k in ('normalized_x','normalized_y','normalized_end_x','normalized_end_y')}
    report={'matches':len(data['matches']),'players':len({r['player_id'] for r in data['players']}),
        'player_match_rows':len(data['players']),'events':total,'aggregate_stat_rows':len(data['player_match_aggregate_stats']),
        'event_type_counts':dict(Counter(e['event_type'] for e in events)),
        'missing_player_id_pct':missing('player_id'),'missing_coordinate_pct':missing('normalized_x'),
        'missing_end_coordinate_pct':missing('normalized_end_x'),
        'duplicate_events':total-len({(r['data_source'],r['source_match_id'],r['source_event_id']) for r in events}),
        'coordinate_ranges':ranges,'seasons':sorted({m['season'] for m in data['matches']}),
        'competitions':sorted({m['competition'] for m in data['matches']}),
        'unknown_minutes_rows':sum(p['minutes_played'] is None for p in data['players'])}
    # Targets must be verified source IDs, never player-name matching.
    for label,ids in (targets or {'Wirtz':{'statsbomb:player:40724'},'Palmer':set()}).items():
        report[label+'_event_rows']=sum(r['player_id'] in ids for r in events)
        report[label+'_aggregate_rows']=sum(r['player_id'] in ids for r in data['player_match_aggregate_stats'])
    return report
