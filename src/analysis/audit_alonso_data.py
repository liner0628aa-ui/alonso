"""Audit the downloaded official catalogue/files with the existing receipt cache."""
import json
from pathlib import Path
from src.data.sources.statsbomb import StatsBombAdapter
from src.data.ingestion import inspect_360_optional, read_dataset
from src.data.sources.base import utc_now


def main():
    a=StatsBombAdapter(offline=True)
    catalogue=a.cache.load('competitions.json')
    processed_ids={m['source_match_id'] for m in read_dataset('data/processed')['matches'] if m['data_source']=='statsbomb'}
    result={'audited_at':utc_now(),'source':'https://github.com/statsbomb/open-data',
            'scope':'Bundesliga Alonso-Leverkusen; full listed target seasons',
            'prior_ingested_match_ids':['3895052','3895292'],
            'manager_filter':'Existing match metadata: team 904 and manager 1000310; manager_period remains NULL. 2022/23 absent so pre-appointment exclusion has no candidate rows.',
            'seasons':{}}
    for season in ('2022/2023','2023/2024'):
        entries=[c for c in catalogue if c['competition_id']==9 and c['season_name']==season]
        if not entries:
            result['seasons'][season]={'published':False,'total_available_matches':0,'alonso_leverkusen_matches':0,
                                     'event_matches':0,'lineup_matches':0,'three_sixty_matches':0,
                                     'previously_ingested':0,'additional_ingested':0,'reason':'Season absent from official competitions.json'}
            continue
        matches=a.load_matches(9,season)
        target=[m for m in matches if any(m[s][s+'_id']==904 and any(v['id']==1000310 for v in m[s].get('managers',[])) for s in ('home_team','away_team'))]
        rows=[]
        for m in sorted(target,key=lambda m:m['match_date']):
            mid=str(m['match_id']);events=a.load_events(mid);lineups=a.load_lineups(mid)
            frames=a.load_360(mid)
            event_ids={e['id'] for e in events}
            rows.append(dict(match_id=mid,match_date=m['match_date'],events=len(events),lineup_teams=len(lineups),
                             raw_360_frames=len(frames) if frames is not None else None,
                             orphan_360_uuids=sum(f['event_uuid'] not in event_ids for f in frames) if frames is not None else None,
                             previously_ingested=mid in result['prior_ingested_match_ids'],
                             currently_ingested=mid in processed_ids,
                             three_sixty=inspect_360_optional(a,mid,events)))
        result['seasons'][season]=dict(published=True,total_available_matches=len(matches),alonso_leverkusen_matches=len(target),
            event_matches=sum(r['events']>0 for r in rows),lineup_matches=sum(r['lineup_teams']==2 for r in rows),
            three_sixty_file_matches=sum(r['raw_360_frames'] is not None for r in rows),
            three_sixty_matches=sum(r['three_sixty']['status']=='verified_uuid_join' for r in rows),
            previously_ingested=sum(r['previously_ingested'] for r in rows),
            additional_ingested=sum(not r['previously_ingested'] and r['currently_ingested'] for r in rows),
            successfully_ingested=sum(r['currently_ingested'] for r in rows),
            downloaded_not_ingested=sum(not r['currently_ingested'] for r in rows),matches=rows)
    result['source_receipts']=a.cache.receipts
    out=Path('outputs/wirtz_alonso_role_mvp');out.mkdir(parents=True,exist_ok=True)
    (out/'available_data_audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:{x:y for x,y in v.items() if x!='matches'} for k,v in result['seasons'].items()},indent=2))

if __name__=='__main__':main()
