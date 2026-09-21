"""StatsBomb Open Data adapter. Event-team coordinates already attack toward x=120.

Do not flip second-half or non-possession-team events. See the official specification
Appendix 2 and pass-angle definition; orientation assumption is recorded in manifest.
"""
from dataclasses import asdict
from urllib.error import HTTPError
from src.data.schema import NormalizedEvent, PlayerMatch
from src.data.coordinate_normalization import normalize_coordinates
from .base import JSONCache, namespace

SOURCE = 'statsbomb'
BASE_URL = 'https://raw.githubusercontent.com/statsbomb/open-data/master/data'
LICENSE_NOTICE = ('Data source: StatsBomb Open Data. Research/non-commercial use only; '
                  'do not redistribute source or processed data. Publications must credit StatsBomb '
                  'and display its logo. See the StatsBomb Public Data User Agreement (2023-09-08). '
                  'The agreement asks users to register their interest at the resource centre.')
TAXONOMY = {'Pass':'PASS','Carry':'CARRY','Shot':'SHOT','Dribble':'DRIBBLE',
            'Ball Receipt*':'RECEIPT','Pressure':'PRESSURE','Interception':'INTERCEPTION',
            'Ball Recovery':'RECOVERY','Foul Committed':'FOUL','Foul Won':'FOUL'}
PERIOD_BASE = {1:0,2:45*60,3:90*60,4:105*60}


def discover_season(competitions, competition, season):
    matches = [r['season_id'] for r in competitions if r['competition_id']==competition and r['season_name']==season]
    if len(matches)!=1:
        raise ValueError(f'Expected exactly one source season: {competition}/{season}; found {matches}')
    return matches[0]


def _name(value):
    return value.get('name') if isinstance(value, dict) else None


def _token(value):
    return value.upper().replace(' ', '_').replace('-', '_') if value else None


def _clock(value):
    parts = [float(x) for x in value.split(':')]
    if len(parts)==2: return parts[0]*60+parts[1]
    if len(parts)==3: return parts[0]*3600+parts[1]*60+parts[2]
    raise ValueError('Invalid source timestamp')


def lineup_minutes(player, events):
    """Position intervals + explicit period ends. Unknown beats guessed minutes.

    Convert source nominal match clocks to elapsed period time. Added time is
    included once; half-time breaks are excluded. Intervals merged across role changes.
    Temporary player-off/on makes duration unknown because lineup coverage can omit it.
    """
    positions = player.get('positions', [])
    pid = player['player_id']
    if any(e.get('player',{}).get('id')==pid and _name(e.get('type')) in {'Player Off','Player On'} for e in events):
        return None, 'unknown:temporary_off_pitch'
    if not positions:
        return None, 'unknown:no_position_intervals'
    ends = {}
    for e in events:
        if _name(e.get('type'))=='Half End' and e['period'] in PERIOD_BASE:
            ends[e['period']] = max(ends.get(e['period'],0), _clock(e['timestamp']))
    if not ends or max(ends)<2 or any(p not in ends for p in range(1,max(ends)+1)):
        return None, 'unknown:missing_period_ends'
    offsets = {p:sum(ends[q] for q in ends if q<p) for p in ends}
    def absolute(clock, period):
        local = _clock(clock)-PERIOD_BASE[period]
        if local<0 or local>ends[period]+1:
            raise ValueError('Lineup clock outside period')
        return offsets[period]+min(local,ends[period])
    try:
        intervals=[]
        for position in positions:
            start=absolute(position['from'],position['from_period'])
            if position.get('to') is None:
                if position.get('end_reason')!='Final Whistle':
                    return None, 'unknown:open_position_interval'
                end=sum(ends.values())
            else:
                end=absolute(position['to'],position['to_period'])
            if end<start: raise ValueError('Reversed interval')
            intervals.append((start,end))
        merged=[]
        for start,end in sorted(intervals):
            if merged and start<=merged[-1][1]+0.01:
                merged[-1]=(merged[-1][0],max(end,merged[-1][1]))
            else: merged.append((start,end))
        return sum(end-start for start,end in merged)/60, 'lineup_intervals_plus_half_end;second_resolution'
    except (KeyError,TypeError,ValueError):
        return None, 'unknown:inconsistent_position_intervals'


class StatsBombAdapter:
    source_name = SOURCE
    def __init__(self, raw_dir='data/raw/statsbomb', offline=False):
        self.cache=JSONCache(raw_dir,BASE_URL,offline)

    def load_matches(self, competition=9, season='2023/2024'):
        competitions=self.cache.load('competitions.json',refresh=True)
        sid=discover_season(competitions,competition,season)
        return self.cache.load(f'matches/{competition}/{sid}.json')

    def load_lineups(self, match_id): return self.cache.load(f'lineups/{match_id}.json')
    def load_events(self, match_id): return self.cache.load(f'events/{match_id}.json')
    def load_aggregate_match_stats(self, match_id): return []

    def load_360(self, match_id):
        try: return self.cache.load(f'three-sixty/{match_id}.json')
        except HTTPError as exc:
            if exc.code==404: return None
            raise

    def normalize_match(self, m):
        row={'match_id':namespace(SOURCE,'match',m['match_id']),'source_match_id':str(m['match_id']),
             'competition':m['competition']['competition_name'],'season':m['season']['season_name'],
             'match_date':m['match_date'],'home_score':m.get('home_score'),'away_score':m.get('away_score'),
             'data_source':SOURCE}
        for side in ('home','away'):
            team=m[side+'_team']; managers=team.get('managers',[])
            manager=managers[0] if len(managers)==1 else {}
            row.update({side+'_team_id':namespace(SOURCE,'team',team[side+'_team_id']),
                        side+'_team_name':team[side+'_team_name'],
                        side+'_manager_id':namespace(SOURCE,'manager',manager.get('id')),
                        side+'_manager':manager.get('name'),side+'_formation':None})
        return row

    def normalize_player(self, p, team, match, events):
        side='home' if namespace(SOURCE,'team',team['team_id'])==match['home_team_id'] else 'away'
        opponent='away' if side=='home' else 'home'
        positions=p.get('positions',[])
        starter=any(x.get('start_reason')=='Starting XI' for x in positions)
        starting=next((x.get('position') for x in positions if x.get('start_reason')=='Starting XI'),None)
        minutes,method=lineup_minutes(p,events)
        formation=None
        for e in events:
            if e.get('team',{}).get('id')==team['team_id'] and _name(e.get('type'))=='Starting XI':
                ids=[x['player']['id'] for x in e['tactics']['lineup']]
                starter=p['player_id'] in ids
                if starter: formation=str(e['tactics']['formation'])
        row=PlayerMatch(player_id=namespace(SOURCE,'player',p['player_id']),player_name=p['player_name'],
            team_id=namespace(SOURCE,'team',team['team_id']),team_name=team['team_name'],
            opponent_id=match[opponent+'_team_id'],opponent_name=match[opponent+'_team_name'],
            match_id=match['match_id'],competition=match['competition'],season=match['season'],match_date=match['match_date'],
            data_source=SOURCE,source_match_id=match['source_match_id'],source_player_id=str(p['player_id']),
            source_team_id=str(team['team_id']),source_opponent_id=match[opponent+'_team_id'].split(':')[-1],
            minutes_played=minutes,home_away=side,manager=match[side+'_manager'],manager_id=match[side+'_manager_id'],
            starting_position=starting,nominal_position=positions[0]['position'] if positions else None,formation=formation,
            event_data_available=bool(events),spatial_data_available=any(e.get('player',{}).get('id')==p['player_id'] and e.get('location') is not None for e in events))
        row.validate()
        result=asdict(row)
        for key in ('features','feature_status','missing_reasons','definition_ids'): result.pop(key)
        result.update(shirt_number=p.get('jersey_number'),starter=starter,minutes_method=method)
        return result

    def normalize_event(self, e, match_id):
        original=_name(e.get('type'))
        event_type=TAXONOMY.get(original,'OTHER')
        key={'Ball Receipt*':'ball_receipt','Goal Keeper':'goalkeeper','50/50':'50_50'}.get(original,(original or '').lower().replace(' ','_'))
        detail=e.get(key,{})
        if original=='Duel' and _name(detail.get('type'))=='Tackle': event_type='TACKLE'
        source_id=str(e.get('id') or f"index:{e['index']}")
        location=e.get('location'); end=detail.get('end_location')
        coords=normalize_coordinates(*(location[:2] if location is not None else (None,None)),
            *(end[:2] if end is not None else (None,None)),width=120,height=80,direction='left_to_right',y_origin='top')
        outcome=_token(_name(detail.get('outcome')))
        # Pass and receipt omit outcome on completion in the official specification.
        if original in ('Pass','Ball Receipt*') and 'outcome' not in detail: outcome='COMPLETE'
        row=NormalizedEvent(match_id=namespace(SOURCE,'match',match_id),event_id=namespace(SOURCE,'event',f'{match_id}:{source_id}'),
            data_source=SOURCE,source_match_id=str(match_id),source_event_id=source_id,
            event_index=e['index'],period=e['period'],minute=e['minute'],second=e['second'],event_type=event_type,
            player_id=namespace(SOURCE,'player',e.get('player',{}).get('id')),team_id=namespace(SOURCE,'team',e.get('team',{}).get('id')),
            source_player_id=str(e['player']['id']) if e.get('player') else None,
            source_team_id=str(e['team']['id']) if e.get('team') else None,
            outcome=outcome,body_part=_token(_name(detail.get('body_part'))),under_pressure=e.get('under_pressure'),
            possession_id=str(e['possession']) if e.get('possession') is not None else None,
            play_pattern=_token(_name(e.get('play_pattern'))),coordinate_transform='statsbomb-event-team-120x80-ltr-top-v1',**coords)
        row.validate()
        result=asdict(row)
        result.update(timestamp=e.get('timestamp'),event_subtype=_token(_name(detail.get('type'))),
                      related_player_id=namespace(SOURCE,'player',detail.get('recipient',detail.get('replacement',{})).get('id')))
        return result
