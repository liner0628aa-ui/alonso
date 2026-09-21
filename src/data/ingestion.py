"""Small reproducible ingestion entry point. No feature engineering or models."""
import argparse
from dataclasses import fields
import json
from pathlib import Path
import shutil
import tempfile
from typing import get_args
from urllib.error import URLError
import pyarrow as pa
import pyarrow.parquet as pq
from src.data.schema import NormalizedEvent, PlayerMatch, SCHEMA_VERSION
from src.data.sources.base import namespace, utc_now, sha256
from src.data.sources.statsbomb import StatsBombAdapter, LICENSE_NOTICE
from src.data.sources.aggregate_csv import AggregateCSVAdapter, RAW_STAT_COLUMNS
from src.data.schema import FEATURES
from src.data.validation import validate_dataset, quality_report

TABLES=('matches','players','events','player_match_aggregate_stats')


def _dataclass_fields(cls, exclude=()):
    result=[]
    for f in fields(cls):
        if f.name in exclude: continue
        typ=next((t for t in get_args(f.type) if t is not type(None)),f.type)
        arrow={str:pa.string(),int:pa.int64(),float:pa.float64(),bool:pa.bool_()}[typ]
        result.append(pa.field(f.name,arrow))
    return result


PLAYER_FIELDS=_dataclass_fields(PlayerMatch,('features','feature_status','missing_reasons','definition_ids'))+[
    pa.field('shirt_number',pa.int64()),pa.field('starter',pa.bool_()),pa.field('minutes_method',pa.string())]
MATCH_FIELDS=[pa.field(k,pa.string()) for k in ('match_id','source_match_id','competition','season','match_date',
    'home_team_id','home_team_name','away_team_id','away_team_name','home_manager_id','away_manager_id',
    'home_manager','away_manager','home_formation','away_formation','data_source')]+[
    pa.field('home_score',pa.int64()),pa.field('away_score',pa.int64())]
SCHEMAS={'matches':pa.schema(MATCH_FIELDS),'players':pa.schema(PLAYER_FIELDS),
    'events':pa.schema(_dataclass_fields(NormalizedEvent)+[pa.field(n,pa.string()) for n in ('timestamp','event_subtype','related_player_id')]),
    'player_match_aggregate_stats':pa.schema(PLAYER_FIELDS+[
        pa.field(k,pa.int64() if k=='touches_att_third_raw' or FEATURES[k]['dtype']=='int' else pa.float64()) for k in RAW_STAT_COLUMNS])}


def build_statsbomb_dataset(adapter, matches, lineups, events):
    data={t:[] for t in TABLES}
    for raw in matches:
        source_id=str(raw['match_id'])
        match=adapter.normalize_match(raw)
        source_events=sorted(events[source_id],key=lambda e:e['index'])
        for e in source_events:
            if e['type']['name']=='Starting XI':
                side='home' if namespace(adapter.source_name,'team',e['team']['id'])==match['home_team_id'] else 'away'
                match[side+'_formation']=str(e['tactics']['formation'])
        data['matches'].append(match)
        for team in lineups[source_id]:
            if namespace(adapter.source_name,'team',team['team_id']) not in (match['home_team_id'],match['away_team_id']):
                raise ValueError('Lineup team outside fixture')
            data['players'].extend(adapter.normalize_player(p,team,match,source_events) for p in team['lineup'])
        data['events'].extend(adapter.normalize_event(e,source_id) for e in source_events)
    validate_dataset(data)
    return data


def build_aggregate_dataset(adapter, match_limit):
    data={t:[] for t in TABLES}
    for match in adapter.load_matches()[:match_limit]:
        data['matches'].append(match)
        for raw in adapter.load_aggregate_match_stats(match['source_match_id']):
            row=adapter.normalize_aggregate_stat_row(raw)
            data['player_match_aggregate_stats'].append(row)
            data['players'].append(adapter.normalize_player(row))
    validate_dataset(data)
    return data


def read_dataset(output):
    output=Path(output)
    manifest=json.loads((output/'manifest.json').read_text()) if (output/'manifest.json').exists() else {}
    data={}
    for name in TABLES:
        path=output/(name+'.parquet')
        expected=manifest.get('processed_files',{}).get(path.name)
        if expected and sha256(path.read_bytes())!=expected:
            raise ValueError('Incomplete or modified processed snapshot')
        table=pq.read_table(path)
        if table.schema!=SCHEMAS[name]: raise ValueError(f'Unexpected reloaded schema: {name}')
        data[name]=table.to_pylist()
    validate_dataset(data)
    return data


def save_dataset(data, output, manifest):
    """Replace a complete slice, never append. Validate staged roundtrip before publish.

    Manifest written last is the commit marker; checksums detect interrupted multi-file
    replacement. This is not a concurrent-writer database.
    """
    validate_dataset(data)
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.stage-',dir=output) as tmp:
        stage=Path(tmp)
        for name in TABLES:
            expected=set(SCHEMAS[name].names)
            if any(set(row)!=expected for row in data[name]): raise ValueError(f'Column drift in {name}')
            table=pa.Table.from_pylist(data[name],schema=SCHEMAS[name])
            pq.write_table(table,stage/(name+'.parquet'),compression='zstd')
        reloaded=read_dataset(stage)
        if reloaded!=data: raise ValueError('Roundtrip changed canonical values')
        doc=dict(manifest)
        doc.update(schema_version=SCHEMA_VERSION,ingestion_version='3.0',processed_at=utc_now(),
                   match_count=len(data['matches']),event_count=len(data['events']),
                   aggregate_stat_count=len(data['player_match_aggregate_stats']),
                   processed_files={p.name:sha256(p.read_bytes()) for p in stage.glob('*.parquet')})
        (stage/'manifest.json').write_text(json.dumps(doc,indent=2,ensure_ascii=False)+'\n')
        (stage/'quality_report.json').write_text(json.dumps(quality_report(data,doc.get('target_player_ids')),indent=2,ensure_ascii=False)+'\n')
        for name in (*[t+'.parquet' for t in TABLES],'quality_report.json','manifest.json'):
            (stage/name).replace(output/name)
    read_dataset(output)


def inspect_360(adapter, match_id, events):
    try:
        frames=adapter.load_360(match_id)
    except FileNotFoundError as exc:
        return {'status':'not_cached','frames':None,'reason':str(exc)}
    except (URLError, TimeoutError) as exc:
        return {'status':'access_failed','frames':None,'reason':str(exc)}
    if frames is None:
        return {'status':'not_found_404','frames':0}
    ids={e['id'] for e in events}
    frame_ids=[r['event_uuid'] for r in frames]
    if len(frame_ids)!=len(set(frame_ids)) or not set(frame_ids)<=ids:
        raise ValueError('360 UUID integrity failure')
    return {'status':'verified_uuid_join','frames':len(frames),
            'event_coverage':len(frames)/len(events) if events else None,
            'storage':'raw only; no tracking reconstruction'}


def inspect_360_optional(adapter, match_id, events):
    """Keep optional malformed/linkage data out without discarding valid events."""
    try:
        return inspect_360(adapter, match_id, events)
    except (ValueError, KeyError, TypeError) as exc:
        return {"status": "invalid_linkage", "frames": None, "reason": str(exc)}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',choices=['statsbomb','approved-csv'],default='statsbomb')
    parser.add_argument('--competition',type=int,default=9)
    parser.add_argument('--season',default='2023/2024')
    parser.add_argument('--match-limit',type=int,default=2)
    parser.add_argument('--match-id',action='append',help='Optional explicit IDs within the selected team/season')
    parser.add_argument('--team-id',type=int,default=904)
    parser.add_argument('--manager-id',type=int,default=1000310,help='Verified StatsBomb Alonso ID from Phase 1 match metadata')
    parser.add_argument('--raw-dir',type=Path,default=Path('data/raw'))
    parser.add_argument('--output-dir',type=Path,default=Path('data/processed'))
    parser.add_argument('--offline',action='store_true',help='Re-read cached catalogue; network disabled explicitly')
    parser.add_argument('--aggregate-file',type=Path)
    parser.add_argument('--aggregate-metadata',type=Path)
    args=parser.parse_args(argv)
    if args.match_limit<1: parser.error('--match-limit must be positive')
    if args.source=='statsbomb':
        a=StatsBombAdapter(args.raw_dir/'statsbomb',args.offline)
        matches=a.load_matches(args.competition,args.season)
        def selected(m):
            for side in ('home_team','away_team'):
                t=m[side]
                if t[side+'_id']==args.team_id and any(v['id']==args.manager_id for v in t.get('managers',[])): return True
            return False
        matches=sorted([m for m in matches if selected(m)],key=lambda m:(m['match_date'],m['match_id']))
        if args.match_id:
            if not set(args.match_id)<={str(m['match_id']) for m in matches}: raise ValueError('Requested match not in team/manager/season filter')
            matches=[m for m in matches if str(m['match_id']) in args.match_id]
        matches=matches[:args.match_limit]
        if not matches: raise ValueError('No matches satisfy source filter')
        lineups={};events={};frames={}
        for m in matches:
            mid=str(m['match_id'])
            lineups[mid]=a.load_lineups(mid);events[mid]=a.load_events(mid)
            frames[mid]=inspect_360_optional(a,mid,events[mid])
        data=build_statsbomb_dataset(a,matches,lineups,events)
        receipts=a.cache.receipts
        fingerprint=sha256(json.dumps({k:v['sha256'] for k,v in receipts.items()},sort_keys=True).encode())
        manifest={'source':'statsbomb','source_version':'content-snapshot:'+fingerprint,
            'source_competition':args.competition,'source_season':args.season,
            'retrieved_at':max(r['retrieved_at'] for r in receipts.values()),'raw_files':receipts,
            'coordinate_system':'source 120x80; canonical 0-100 event-team left-to-right, no half-time flip',
            'event_definition_notes':'Open Data spec v1.1; preserve absent pressure as null. Pass/receipt absent outcome maps COMPLETE.',
            'license_notice':LICENSE_NOTICE,'license_url':'https://github.com/statsbomb/open-data/blob/master/LICENSE.pdf',
            'three_sixty':frames,'target_player_ids':{'Wirtz':['statsbomb:player:40724'],'Palmer':[]},
            'limitations':['No approved Chelsea/Palmer match aggregate acquired; no synthetic real rows.',
                'Player metadata includes unused lineup members; unknown minutes remain null.',
                'Manager ID supplied by match; manager_period not invented.',
                'Data remains local; external redistribution not authorized.']}
    else:
        if not args.aggregate_file or not args.aggregate_metadata: parser.error('Local CSV and provenance JSON required')
        metadata=json.loads(args.aggregate_metadata.read_text())
        a=AggregateCSVAdapter(args.aggregate_file,metadata)
        data=build_aggregate_dataset(a,args.match_limit)
        if not data['matches']: raise ValueError('Empty aggregate slice')
        raw=args.raw_dir/a.source_name;raw.mkdir(parents=True,exist_ok=True)
        digest=sha256(args.aggregate_file.read_bytes())
        shutil.copyfile(args.aggregate_file,raw/(digest+'.csv'))
        shutil.copyfile(args.aggregate_metadata,raw/(digest+'.metadata.json'))
        manifest=dict(metadata,source=a.source_name,retrieved_at=metadata.get('retrieved_at'),
                      loaded_at=utc_now(),raw_sha256=digest,coordinate_system='none:aggregate-only')
    manifest['competitions']=sorted({r['competition'] for r in data['matches']})
    manifest['seasons']=sorted({r['season'] for r in data['matches']})
    save_dataset(data,args.output_dir,manifest)
    print(json.dumps(quality_report(data,manifest.get('target_player_ids')),indent=2))


if __name__=='__main__': main()
