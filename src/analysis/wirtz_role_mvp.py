"""Reproducible event-only report. Definitions: docs/tactical_features_mvp.md."""
import csv
import json
from collections import defaultdict
from pathlib import Path
from src.config.pitch_zones import classify_zone, LANE_NAMES
from src.data.schema import per90
from src.data.ingestion import read_dataset
from src.data.sources.statsbomb import StatsBombAdapter, LICENSE_NOTICE
from src.data.sources.base import sha256

WIRTZ = 'statsbomb:player:40724'
TEAM = 'statsbomb:team:904'
TOUCH_TYPES = {'PASS', 'CARRY', 'SHOT', 'DRIBBLE', 'RECEIPT'}


def touches(events):
    return [e for e in events if e['event_type'] in TOUCH_TYPES and
            (e['event_type'] != 'RECEIPT' or e['outcome'] == 'COMPLETE')]


def located(events):
    return [e for e in events if e['normalized_x'] is not None]


def action_flags(e):
    result = dict(forward=False, progressive=False, final_third_entry=False, penalty_area_entry=False)
    if e['event_type'] not in {'PASS', 'CARRY'}:
        return result
    x, y, ex, ey = (e[k] for k in ('normalized_x','normalized_y','normalized_end_x','normalized_end_y'))
    if x is None or ex is None:
        return dict.fromkeys(result)
    result['forward'] = ex > x
    if e['event_type'] == 'PASS' and e['outcome'] != 'COMPLETE':
        return result
    result['progressive'] = ex - x >= 10 - 1e-9
    result['final_third_entry'] = x < 200/3 <= ex
    result['penalty_area_entry'] = not classify_zone(x,y)[2] and classify_zone(ex,ey)[2]
    return result


def metrics(events, minutes):
    events = [e for e in events if e['period'] in (1,2,3,4)]
    ts = touches(events); pts = located(ts)
    rs = [e for e in events if e['event_type']=='RECEIPT' and e['outcome']=='COMPLETE']
    rp = located(rs)
    m = dict(minutes=minutes, events_analysed=len(events), touches_proxy=len(ts),
             located_touches_proxy=len(pts), receptions=len(rs), located_receptions=len(rp))
    for label, rows in [('touch',pts),('reception',rp)]:
        for axis in ('x','y'):
            m[f'avg_{label}_{axis}'] = sum(e['normalized_'+axis] for e in rows)/len(rows) if rows else None
    lanes = [classify_zone(e['normalized_x'],e['normalized_y'])[0] for e in pts]
    for lane in LANE_NAMES:
        m[lane+'_share'] = lanes.count(lane)/len(lanes) if lanes else None
    for name, predicate in [('left',lambda y:y<40),('central',lambda y:40<=y<60),('right',lambda y:y>=60),
                             ('halfspace',lambda y:20<=y<40 or 60<=y<80)]:
        m[name+'_share'] = sum(predicate(e['normalized_y']) for e in pts)/len(pts) if pts else None
    m['final_third_involvement'] = sum(e['normalized_x']>=200/3 for e in pts)
    m['final_third_share'] = m['final_third_involvement']/len(pts) if pts else None
    for name, typ in [('passes','PASS'),('carries','CARRY'),('shots','SHOT'),('pressures','PRESSURE'),
                      ('tackles','TACKLE'),('interceptions','INTERCEPTION'),('recoveries','RECOVERY')]:
        m[name] = sum(e['event_type']==typ for e in events)
    m['passes_completed'] = sum(e['event_type']=='PASS' and e['outcome']=='COMPLETE' for e in events)
    m['pass_completion'] = m['passes_completed']/m['passes'] if m['passes'] else None
    m['forward_passes'] = sum(e['event_type']=='PASS' and action_flags(e)['forward'] is True for e in events)
    for name,typ in [('passes','PASS'),('carries','CARRY')]:
        m[name+'_unknown_endpoints'] = sum(e['event_type']==typ and action_flags(e)['forward'] is None for e in events)
        m['progressive_'+name] = sum(e['event_type']==typ and action_flags(e)['progressive'] is True for e in events)
        for entry in ('final_third_entry','penalty_area_entry'):
            m[name+'_'+entry] = sum(e['event_type']==typ and action_flags(e)[entry] is True for e in events)
    for entry in ('final_third','penalty_area'):
        m[entry+'_entries'] = m['passes_'+entry+'_entry']+m['carries_'+entry+'_entry']
    m['defensive_actions'] = sum(m[k] for k in ('pressures','tackles','interceptions','recoveries'))
    for k in ('touches_proxy','receptions','passes','carries','shots','progressive_passes','progressive_carries','defensive_actions'):
        m[k+'_p90'] = per90(m[k], minutes)
    m['nearest_defender_distance'] = None # advanced 360 feature is not implemented
    return m


def creation_metrics(events, raw):
    """Provider qualifiers shared by Wirtz and team reports; raw is receipt-checked."""
    events = [e for e in events if e["period"] in (1,2,3,4)]
    return dict(shot_assists=sum(bool(raw[(e["source_match_id"],e["source_event_id"])].get("pass",{}).get("shot_assist")) for e in events),
                xg=sum(raw[(e["source_match_id"],e["source_event_id"])]["shot"]["statsbomb_xg"] for e in events if e["event_type"]=="SHOT"))


def write_csv(path, rows):
    if not rows:
        raise ValueError('Refuse empty report CSV')
    with path.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    out=Path('outputs/wirtz_alonso_role_mvp');out.mkdir(parents=True,exist_ok=True)
    data=read_dataset('data/processed')
    manifest=json.loads(Path('data/processed/manifest.json').read_text())
    a=StatsBombAdapter(offline=True)
    for match in data['matches']:
        side = 'home' if match['home_team_id']==TEAM else 'away'
        if (match['data_source']!='statsbomb' or match['season']!='2023/2024' or
            match['competition']!='1. Bundesliga' or match[side+'_team_id']!=TEAM or
            match[side+'_manager_id']!='statsbomb:manager:1000310'):
            raise ValueError('Report requires verified Bundesliga 2023/24 Alonso-Leverkusen fixtures')
    by_match=defaultdict(list)
    for e in data['events']:
        if e['player_id']==WIRTZ and e['team_id']==TEAM and e['period'] in (1,2,3,4):
            by_match[e['match_id']].append(e)
    players=sorted([p for p in data['players'] if p['player_id']==WIRTZ and p['team_id']==TEAM
                    and (p['minutes_played'] is not None and p['minutes_played']>0 or p['match_id'] in by_match)],
                   key=lambda p:p['match_date'])
    raw={}
    for p in players:
        mid=p['source_match_id']; payload=a.load_events(mid)
        receipt=a.cache.receipts[f'events/{mid}.json']
        if receipt['sha256']!=manifest['raw_files'][f'events/{mid}.json']['sha256']:
            raise ValueError('Report qualifiers differ from ingestion snapshot')
        raw.update({(mid,e['id']):e for e in payload})
    rows=[]; all_events=[]
    for p in players:
        es=by_match[p['match_id']];all_events.extend(es)
        m=metrics(es,p['minutes_played'])
        m.update(creation_metrics(es,raw))
        rows.append(dict(match_id=p['match_id'],match_date=p['match_date'],opponent=p['opponent_name'],
                         home_away=p['home_away'],starting_position=p['starting_position'],**m))
    unknown=sum(p['minutes_played'] is None for p in players)
    known_minutes=sum(p['minutes_played'] or 0 for p in players)
    total=metrics(all_events,known_minutes if not unknown else None)
    total.update(matches=len(players),unknown_minutes_matches=unknown,known_minutes=known_minutes,
                 shot_assists=sum(r['shot_assists'] for r in rows),xg=sum(r['xg'] for r in rows))
    write_csv(out/'wirtz_role_metrics.csv',rows)
    write_csv(out/'wirtz_role_totals.csv',[total])
    export=[]
    for e in all_events:
        export.append({k:e[k] for k in ('match_id','source_event_id','event_type','period','minute','normalized_x',
                                        'normalized_y','normalized_end_x','normalized_end_y','outcome')} |
                      dict(touch_proxy=e in touches([e]),**action_flags(e)))
    write_csv(out/'wirtz_event_features.csv',export)
    write_csv(out/'shot_locations.csv',[dict(match_id=e['match_id'],event_id=e['source_event_id'],
        x=e['normalized_x'],y=e['normalized_y'],outcome=e['outcome'],
        xg=raw[(e['source_match_id'],e['source_event_id'])]['shot']['statsbomb_xg']) for e in all_events if e['event_type']=='SHOT'])
    plt.rcParams.update({'figure.facecolor':'#f8fafc','axes.facecolor':'#f8fafc','font.size':10})
    def pitch(ax,title):
        ax.add_patch(Rectangle((0,0),100,100,fill=False,color='#334155'))
        ax.add_patch(Rectangle((85,22.5),15,55,fill=False,color='#334155'))
        ax.axvline(50,color='#94a3b8',lw=.8)
        ax.set(xlim=(0,100),ylim=(100,0),xlabel='Attack direction → (normalized x)',ylabel='Left ← y → Right',title=title)
        ax.set_aspect(80/120)
    def save(fig,name):
        fig.text(.02,.015,'Data: StatsBomb Open Data | Bundesliga 2023/24 | Event-only observed behaviour',fontsize=8,color='#475569')
        fig.tight_layout(rect=(0,.045,1,1));fig.savefig(out/name,dpi=170);plt.close(fig)
    pts=located(touches(all_events));recs=located([e for e in all_events if e['event_type']=='RECEIPT' and e['outcome']=='COMPLETE'])
    for name,es,title in [('touch_heatmap.png',pts,'On-ball event proxy (not physical touch count)'),
                         ('reception_heatmap.png',recs,'Completed Ball Receipt* events')]:
        fig,ax=plt.subplots(figsize=(9,6));pitch(ax,f'Florian Wirtz | {title}\nn={len(es):,}, {len(players)} appearances')
        h=ax.hist2d([e['normalized_x'] for e in es],[e['normalized_y'] for e in es],bins=(20,16),range=((0,100),(0,100)),cmap='YlOrRd',zorder=0)
        fig.colorbar(h[3],ax=ax,label='Event count per bin');save(fig,name)
    fig,axes=plt.subplots(1,2,figsize=(13,5))
    for ax,typ,color in zip(axes,['PASS','CARRY'],['#2563eb','#ea580c']):
        es=[e for e in all_events if e['event_type']==typ and action_flags(e)['progressive']]
        label = 'passes' if typ=='PASS' else 'carries'
        detail = 'completed passes' if typ=='PASS' else 'recorded carries'
        pitch(ax,f'Progressive {label} | n={len(es)}\nΔx ≥ 10; {detail}')
        for e in es:
            ax.annotate('',xy=(e['normalized_end_x'],e['normalized_end_y']),xytext=(e['normalized_x'],e['normalized_y']),
                        arrowprops=dict(arrowstyle='->',color=color,alpha=.22,lw=.8))
    save(fig,'progressive_actions.png')
    fig,ax=plt.subplots(figsize=(9,5));vals=[100*total[k+'_share'] for k in LANE_NAMES]
    ax.bar([k.replace('_',' ') for k in LANE_NAMES],vals,color=['#2563eb','#0d9488','#64748b','#0d9488','#2563eb'])
    for i,v in enumerate(vals):ax.text(i,v+.4,f'{v:.1f}%',ha='center')
    ax.set(ylabel='Share of located on-ball proxy events (%)',title='Wirtz | Five-lane event occupation',ylim=(0,max(vals)+6));save(fig,'zone_occupation.png')
    fig,axes=plt.subplots(2,1,figsize=(12,7),sharex=True)
    axes[0].plot([r['avg_touch_x'] for r in rows],label='Average x');axes[0].plot([r['avg_touch_y'] for r in rows],label='Average y');axes[0].legend();axes[0].set(ylabel='Normalized coordinate',title='Wirtz | Match-to-match observed variation')
    axes[1].plot([r['progressive_passes'] for r in rows],label='Progressive passes');axes[1].plot([r['progressive_carries'] for r in rows],label='Progressive carries');axes[1].legend();axes[1].set(ylabel='Raw count')
    axes[1].set_xticks(range(len(rows)),[r['match_date'][5:] for r in rows],rotation=90);save(fig,'match_role_variation.png')
    team_events=defaultdict(list)
    for e in data['events']:
        if e['team_id']==TEAM and e['period'] in (1,2,3,4) and e['player_id']:
            team_events[e['player_id']].append(e)
    names={p['player_id']:p['player_name'] for p in data['players']};team=[]
    for pid,es in team_events.items():
        m=metrics(es,None)
        if m['located_touches_proxy']>=500:
            team.append(dict(player_id=pid,player_name=names[pid],located_touches_proxy=m['located_touches_proxy'],x=m['avg_touch_x'],y=m['avg_touch_y']))
    write_csv(out/'team_spatial_profiles.csv',team)
    fig,ax=plt.subplots(figsize=(11,7));pitch(ax,f'Leverkusen | Average on-ball event positions\nAll {len(data["matches"])} ingested fixtures; ≥500 located events; not a formation')
    for i,r in enumerate(sorted(team,key=lambda r:r['y'])):
        ax.scatter(r['x'],r['y'],s=70,color='#dc2626' if r['player_id']==WIRTZ else '#2563eb')
        ax.annotate(r['player_name'],(r['x'],r['y']),xytext=(10 if i%2 else -10,12 if i%2 else -12),textcoords='offset points',ha='left' if i%2 else 'right',fontsize=7,arrowprops=dict(arrowstyle='-',lw=.4))
    save(fig,'team_average_positions.png')
    def f(k):
        v=total[k];return 'NULL' if v is None else f'{v:,.2f}' if isinstance(v,float) else f'{v:,}'
    summary=f'''# Wirtz — Alonso-Leverkusen Tactical Role MVP

Observed behaviour in StatsBomb Open Data, Bundesliga 2023/24. No causal claim about coaching instructions and no inferred fixed role label.

- Dataset: {len(data['matches'])} matches, {len(data['events']):,} events. Wirtz: {f('matches')} appearances, {f('events_analysed')} player events analysed.
- 360: {sum(v['status']=='verified_uuid_join' for v in manifest['three_sixty'].values())} fixtures with valid UUID joins; {sum(v['status']=='invalid_linkage' for v in manifest['three_sixty'].values())} excluded for invalid linkage. Downloaded-file availability and orphan counts are recorded in available_data_audit.json.
- Minutes: {f('minutes')} total; {f('known_minutes')} known minutes; {f('unknown_minutes_matches')} appearances with unknown minutes. Existing lineup/period-end method includes stoppage time. Unknown totals/p90 remain NULL.
- Unknown-minute fixtures: {', '.join(p['match_date']+' vs '+p['opponent_name']+' ('+p['source_match_id']+'; '+p['minutes_method']+')' for p in players if p['minutes_played'] is None) or 'none'}.
- Involvement: {f('touches_proxy')} on-ball event proxies, {f('located_touches_proxy')} with coordinates; {f('receptions')} completed receptions ({f('located_receptions')} located). These are event counts, not distinct physical touches.
- Average on-ball event position: ({f('avg_touch_x')}, {f('avg_touch_y')}); average reception: ({f('avg_reception_x')}, {f('avg_reception_y')}) on 0–100 attacking coordinates, y=0 left.
- Spatial shares: left {100*total['left_share']:.2f}%, central {100*total['central_share']:.2f}%, right {100*total['right_share']:.2f}%; half-spaces {100*total['halfspace_share']:.2f}% (overlapping the left/right split).
- Final-third involvement: {f('final_third_involvement')} located on-ball events ({100*total['final_third_share']:.2f}%).
- Passing: {f('passes')} attempts, {f('passes_completed')} completed; {f('forward_passes')} forward attempts; {f('progressive_passes')} completed progressive passes.
- Carrying: {f('carries')} carries; {f('progressive_carries')} progressive carries.
- Endpoint coverage: {f('passes_unknown_endpoints')} passes and {f('carries_unknown_endpoints')} carries have unknown endpoints; progression and entry totals count only evaluable actions. Unknown event flags are NULL.
- Entries: {f('final_third_entries')} into final third, {f('penalty_area_entries')} into penalty area, from completed passes and carries crossing the respective boundary.
- Creation/shooting: {f('shot_assists')} provider-flagged shot-assist passes; {f('shots')} shots, {f('xg')} StatsBomb xG. Shot coordinates and outcomes are in shot_locations.csv. xA and wider shot-creating chains are not estimated.
- Defensive activity (selected event set): {f('defensive_actions')} total = {f('pressures')} pressures + {f('tackles')} tackles + {f('interceptions')} interceptions + {f('recoveries')} recoveries. Counts do not imply defensive success.

## Interpretation and limits

The figures describe event-weighted on-ball behaviour. They do not measure time spent in zones, off-ball movement, a stable team formation or the whole Alonso system. Reception/carry/pass events can describe the same possession sequence, so the touch proxy overweights longer recorded action chains. All situations, including set pieces, are retained. Progression is the local Δx≥10 definition, not a provider-standard progressive metric. Match variation is unadjusted for opponent, score, minutes and possession. Team context uses all ingested fixtures, including Wirtz absences, and a disclosed 500-event display threshold.

360 is only a verified raw UUID link: advanced spatial features remain NULL and are not used here. Unknown minutes are not replaced by 90 or inferred from event counts. No synthetic events enter any output. See ../../docs/tactical_features_mvp.md and available_data_audit.json for definitions and source coverage.

## Attribution

{LICENSE_NOTICE}

Source: https://github.com/statsbomb/open-data . Local research report; before public publication display the official StatsBomb logo as required. No public distribution was performed.
'''
    (out/'role_summary.md').write_text(summary)
    provenance=dict(source=manifest['source'],source_version=manifest['source_version'],
        processed_files=manifest['processed_files'],license_notice=manifest['license_notice'],
        definitions='docs/tactical_features_mvp.md',feature_version='event-mvp-v1',
        code_sha256=sha256(Path(__file__).read_bytes()),
        definitions_sha256=sha256(Path('docs/tactical_features_mvp.md').read_bytes()),
        outputs={p.name:sha256(p.read_bytes()) for p in out.iterdir() if p.suffix in ('.png','.csv','.md')})
    (out/'report_manifest.json').write_text(json.dumps(provenance,indent=2)+'\n')
    print(json.dumps(total,indent=2))

if __name__=='__main__':main()
