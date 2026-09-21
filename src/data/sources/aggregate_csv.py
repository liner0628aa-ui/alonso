"""Permission-gated local match-stat export adapter; no web scraping.

Accepts only provider-reported RAW match counts, never per90 or manufactured events.
There is no currently approved Palmer export in the repository. A column mapping and
provenance manifest are required; the adapter itself does not grant data-use rights.
"""
import csv
from dataclasses import asdict
import math
from pathlib import Path
import re
from src.data.schema import FEATURES, PlayerMatch
from .base import namespace

RAW_STAT_COLUMNS = tuple(k for k in FEATURES if k.endswith('_raw')) + ('touches_att_third_raw',)


class AggregateCSVAdapter:
    def __init__(self, path=None, metadata=None):
        self.path=Path(path) if path else None
        self.metadata=metadata or {}
        for key in ('source_name','source_version','source_url','license_notice','permission_basis','event_definition_notes'):
            if not isinstance(self.metadata.get(key),str) or not self.metadata[key].strip():
                raise ValueError(f'Aggregate export requires provenance: {key}')
        self.source_name=self.metadata['source_name']
        if not re.fullmatch('[a-z][a-z0-9_]*',self.source_name) or self.source_name=='statsbomb':
            raise ValueError('Distinct simple source namespace required')
        self.mapping=self.metadata.get('column_map',{})
        if not self.mapping or not set(self.mapping)<=set(RAW_STAT_COLUMNS):
            raise ValueError('Map only canonical raw stat columns; per90 is prohibited')
        self.rows=None

    def load_matches(self):
        if self.rows is None:
            if self.path is None: raise ValueError('Local export path required')
            with self.path.open(newline='',encoding='utf-8-sig') as f:
                reader=csv.DictReader(f)
                if not set(self.mapping.values())<=set(reader.fieldnames or []):
                    raise ValueError('Mapped source columns absent from CSV header')
                self.rows=list(reader)
        result={}
        for row in self.rows:
            key=row['source_match_id']
            match=self.normalize_match(row)
            if key in result and result[key]!=match: raise ValueError('Conflicting match metadata')
            result[key]=match
        return list(result.values())

    def load_lineups(self): return []
    def load_events(self, match_id): return []
    def load_aggregate_match_stats(self, match_id):
        self.load_matches()
        return [r for r in self.rows if r['source_match_id']==str(match_id)]

    def normalize_match(self, r):
        row=self.normalize_aggregate_stat_row(r)
        side=row['home_away']; other='away' if side=='home' else 'home'
        return {'match_id':row['match_id'],'source_match_id':row['source_match_id'],
                'competition':row['competition'],'season':row['season'],'match_date':row['match_date'],
                'data_source':self.source_name,'home_score':None,'away_score':None,
                side+'_team_id':row['team_id'],side+'_team_name':row['team_name'],
                other+'_team_id':row['opponent_id'],other+'_team_name':row['opponent_name'],
                'home_manager':None,'away_manager':None,'home_manager_id':None,'away_manager_id':None,
                'home_formation':None,'away_formation':None}

    def normalize_player(self, row):
        return {k:v for k,v in row.items() if k not in RAW_STAT_COLUMNS}

    def normalize_aggregate_stat_row(self, r):
        src=self.source_name
        for key in ('source_match_id','source_player_id','source_team_id','source_opponent_id'):
            if not r.get(key): raise ValueError(f'Missing aggregate identity: {key}')
        def number(value):
            if value is None or value=='': return None
            if isinstance(value,bool): raise ValueError('Boolean statistic')
            result=float(value)
            if not math.isfinite(result) or result<0: raise ValueError('Invalid aggregate number')
            return result
        player=PlayerMatch(player_id=namespace(src,'player',r['source_player_id']),
            player_name=r['player_name'],team_id=namespace(src,'team',r['source_team_id']),team_name=r['team_name'],
            opponent_id=namespace(src,'team',r['source_opponent_id']),opponent_name=r['opponent_name'],
            match_id=namespace(src,'match',r['source_match_id']),source_match_id=r['source_match_id'],
            source_player_id=r['source_player_id'],source_team_id=r['source_team_id'],source_opponent_id=r['source_opponent_id'],
            competition=r['competition'],season=r['season'],match_date=r['match_date'],data_source=src,
            minutes_played=number(r.get('minutes_played')),home_away=r['home_away'],
            manager=r.get('manager') or None,manager_id=namespace(src,'manager',r.get('source_manager_id') or None),
            manager_period=r.get('manager_period') or None,nominal_position=r.get('nominal_position') or None)
        stats=dict.fromkeys(RAW_STAT_COLUMNS)
        for canonical,original in self.mapping.items():
            value=number(r.get(original))
            if value is not None:
                integer=canonical=='touches_att_third_raw' or FEATURES[canonical]['dtype']=='int'
                if integer:
                    if not value.is_integer(): raise ValueError('Fractional count in raw export')
                    value=int(value)
                if canonical in FEATURES:
                    player.set_feature(canonical,value,'observed',f"{src}:{self.metadata['source_version']}:{original}")
            stats[canonical]=value
        player.validate()
        result=asdict(player)
        for key in ('features','feature_status','missing_reasons','definition_ids'): result.pop(key)
        result.update(shirt_number=None,starter=None,minutes_method='source_reported' if player.minutes_played is not None else 'unknown:source_not_provided')
        result.update(stats)
        return result
