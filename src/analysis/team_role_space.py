"""Milestone 2: descriptive team-wide PCA/cosine baseline; no predictive model."""
import json
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from src.analysis.wirtz_role_mvp import metrics, creation_metrics, write_csv, TEAM, WIRTZ
from src.data.schema import per90
from src.data.ingestion import read_dataset
from src.data.sources.statsbomb import StatsBombAdapter
from src.data.sources.base import sha256

MIN_MATCH_MINUTES = 30
MIN_SEASON_KNOWN_MINUTES = 450
OUT = Path('outputs/alonso_team_role_space')
# One count/rate representation only. Redundant means/shares and aggregate sums omitted.
FEATURE_SPECS = {
    'avg_touch_x': ('spatial','0–100','Mean located on-ball proxy x; event-weighted, attacking direction'),
    'avg_touch_y': ('spatial','0–100','Mean located on-ball proxy y; 0 = attacking left'),
    'halfspace_share': ('spatial','share','Located proxy events with 20<=y<40 or 60<=y<80 / all located proxy events'),
    'passes_p90': ('involvement','count/90min','All PASS attempts *90 / known match minutes'),
    'forward_pass_rate': ('progression','share','Forward PASS attempts / all PASS attempts; NULL if missing endpoints or no passes'),
    'progressive_passes_p90': ('progression','count/90min','Completed PASS with normalized delta-x>=10 *90 / minutes'),
    'progressive_carries_p90': ('progression','count/90min','CARRY with normalized delta-x>=10 *90 / minutes'),
    'final_third_entries_p90': ('progression','count/90min','Completed PASS or CARRY crossing from x<200/3 to x>=200/3 *90 / minutes'),
    'penalty_area_entries_p90': ('progression','count/90min','Completed PASS or CARRY entering existing proportional box *90 / minutes'),
    'shot_assists_p90': ('creation','count/90min','Raw StatsBomb pass.shot_assist=true count *90 / minutes'),
    'xg_p90': ('attacking','xG/90min','Sum raw StatsBomb shot.statsbomb_xg *90 / minutes'),
    'pressures_p90': ('defensive','count/90min','PRESSURE events *90 / minutes, not successful pressures'),
    'recoveries_p90': ('defensive','count/90min','RECOVERY events *90 / minutes, not success rate'),
    'tackles_p90': ('defensive','count/90min','Duel subtype Tackle events *90 / minutes'),
    'interceptions_p90': ('defensive','count/90min','INTERCEPTION events *90 / minutes'),
}
ROLE_FEATURES = tuple(FEATURE_SPECS)
COUNT_FIELDS = ('touches_proxy','receptions','passes','passes_completed','forward_passes','carries',
                'progressive_passes','progressive_carries','final_third_entries','penalty_area_entries',
                'shots','shot_assists','pressures','recoveries','tackles','interceptions','defensive_actions',
                'final_third_involvement')


def enrich_metrics(base, creation):
    result = dict(base, **creation)
    for key in (*COUNT_FIELDS,'xg'):
        result[key+'_p90'] = per90(result[key], result['minutes'])
    result['forward_pass_rate'] = (result['forward_passes']/result['passes']
        if result['passes'] and result['passes_unknown_endpoints']==0 else None)
    # M1 raw counts remain observed counts. Modelling rates require complete endpoints.
    for kind, fields in [('passes',('progressive_passes_p90','forward_passes_p90')),
                         ('carries',('progressive_carries_p90',))]:
        if result[kind+'_unknown_endpoints']:
            for key in fields: result[key]=None
    if result['passes_unknown_endpoints'] or result['carries_unknown_endpoints']:
        result['final_third_entries_p90']=result['penalty_area_entries_p90']=None
    return result


def exclusion_reason(row):
    reasons=[]
    if row['minutes'] is None: reasons.append('unknown_minutes')
    elif row['minutes']<MIN_MATCH_MINUTES: reasons.append('short_appearance')
    if row['season_known_minutes']<MIN_SEASON_KNOWN_MINUTES: reasons.append('season_minutes_below_threshold')
    if not row['events_analysed']: reasons.append('no_player_events')
    missing=[k for k in ROLE_FEATURES if row[k] is None or not np.isfinite(row[k])]
    if missing: reasons.append('missing_features:'+','.join(missing))
    return ';'.join(reasons)


def weighted_centroid(values, minutes):
    values=np.asarray(values,dtype=float);minutes=np.asarray(minutes,dtype=float)
    if not np.isfinite(values).all() or not np.isfinite(minutes).all() or np.any(minutes<=0):
        raise ValueError('Finite features and positive known minutes required')
    return np.average(values,axis=0,weights=minutes)


def cosine(a,b):
    a=np.asarray(a,dtype=float);b=np.asarray(b,dtype=float)
    denominator=np.linalg.norm(a)*np.linalg.norm(b)
    if denominator<=1e-12:return None
    return float(np.clip(np.dot(a,b)/denominator,-1,1))


def build_rows(data, manifest):
    adapter=StatsBombAdapter(offline=True)
    grouped=defaultdict(list)
    for event in data['events']:
        if event['team_id']==TEAM and event['player_id'] and event['period'] in (1,2,3,4):
            grouped[(event['match_id'],event['player_id'])].append(event)
    qualifiers={}
    for match in data['matches']:
        side='home' if match['home_team_id']==TEAM else 'away'
        if (match['data_source']!='statsbomb' or match['season']!='2023/2024' or match['competition']!='1. Bundesliga'
            or match[side+'_team_id']!=TEAM or match[side+'_manager_id']!='statsbomb:manager:1000310'):
            raise ValueError('Expected verified Alonso-Leverkusen Bundesliga 2023/24 snapshot')
        mid=match['source_match_id'];raw=adapter.load_events(mid)
        if adapter.cache.receipts[f'events/{mid}.json']['sha256']!=manifest['raw_files'][f'events/{mid}.json']['sha256']:
            raise ValueError('Raw qualifiers differ from processed source snapshot')
        lookup={(mid,e['id']):e for e in raw}
        for p in data['players']:
            if p['match_id']==match['match_id'] and p['team_id']==TEAM:
                key=(p['match_id'],p['player_id']);qualifiers[key]=creation_metrics(grouped[key],lookup)
    rows=[];known=defaultdict(float)
    for p in data['players']:
        if p['team_id']==TEAM and p['minutes_played'] is not None: known[p['player_id']]+=p['minutes_played']
    for p in sorted(data['players'],key=lambda p:(p['match_date'],p['player_id'])):
        if p['team_id']!=TEAM:continue
        key=(p['match_id'],p['player_id']);es=grouped[key]
        row={k:p[k] for k in ('player_id','player_name','match_id','match_date','opponent_name','home_away',
                              'starting_position','nominal_position','formation','starter','minutes_method')}
        row.update(enrich_metrics(metrics(es,p['minutes_played']),qualifiers[key]))
        row['season_known_minutes']=known[p['player_id']]
        row['appearance_observed']=bool(es) or (p['minutes_played'] is not None and p['minutes_played']>0)
        row['exclusion_reason']=exclusion_reason(row);row['analysis_eligible']=not row['exclusion_reason']
        rows.append(row)
    return rows


def model_rows(rows):
    from sklearn.preprocessing import StandardScaler
    from sklearn.decomposition import PCA
    selected=[r for r in rows if r['analysis_eligible']]
    x=np.array([[r[k] for k in ROLE_FEATURES] for r in selected])
    scaler=StandardScaler();z=scaler.fit_transform(x)
    if np.any(scaler.var_<=1e-12):raise ValueError('Constant selected feature: revise explicit selection')
    pca=PCA(svd_solver='full');scores=pca.fit_transform(z)
    index=defaultdict(list)
    for i,r in enumerate(selected):
        index[r['player_id']].append(i)
        r.update({k+'_z':float(z[i,j]) for j,k in enumerate(ROLE_FEATURES)})
        r.update(PC1=float(scores[i,0]),PC2=float(scores[i,1]))
    for r in rows:
        if not r['analysis_eligible']:
            r.update({k+'_z':None for k in ROLE_FEATURES});r.update(PC1=None,PC2=None)
    seasons=[];stabilities=[];match_stability=[]
    for pid,indices in sorted(index.items(),key=lambda pair:selected[pair[1][0]]['player_name']):
        rs=[selected[i] for i in indices];weights=np.array([r['minutes'] for r in rs])
        xs=x[indices];zs=z[indices];center=weighted_centroid(zs,weights);rawcenter=weighted_centroid(xs,weights)
        point=pca.transform(center.reshape(1,-1))[0]
        all_rows=[r for r in rows if r['player_id']==pid]
        season=dict(player_id=pid,player_name=rs[0]['player_name'],match_count=len(rs),
                    appearances=sum(r['appearance_observed'] for r in all_rows),lineup_rows=len(all_rows),
                    season_known_minutes=rs[0]['season_known_minutes'],represented_minutes=float(weights.sum()),
                    unknown_minutes_appearances=sum(r['appearance_observed'] and r['minutes'] is None for r in all_rows),
                    nominal_positions=' | '.join(sorted({r['nominal_position'] for r in rs if r['nominal_position']})),
                    PC1=float(point[0]),PC2=float(point[1]))
        for j,k in enumerate(ROLE_FEATURES):
            season.update({k+'_mean':float(rawcenter[j]),k+'_median':float(np.median(xs[:,j])),
                           k+'_std':float(np.std(xs[:,j],ddof=0)),k+'_z':float(center[j]),
                           k+'_z_median':float(np.median(zs[:,j])),k+'_z_std':float(np.std(zs[:,j],ddof=0))})
        seasons.append(season)
        sims=[];loo=[]
        for local,i in enumerate(indices):
            c=cosine(z[i],center)
            other=[j for j in range(len(indices)) if j!=local]
            c_loo=cosine(z[i],weighted_centroid(zs[other],weights[other])) if other else None
            if c is not None:sims.append(c)
            if c_loo is not None:loo.append(c_loo)
            match_stability.append(dict(player_id=pid,player_name=season['player_name'],match_id=selected[i]['match_id'],
                                        minutes=selected[i]['minutes'],cosine_to_centroid=c,leave_one_out_cosine=c_loo))
        stabilities.append(dict(player_id=pid,player_name=season['player_name'],match_count=len(rs),
            valid_cosine_count=len(sims),cosine_mean=float(np.mean(sims)) if sims else None,
            cosine_median=float(np.median(sims)) if sims else None,cosine_std=float(np.std(sims)) if sims else None,
            cosine_p10=float(np.quantile(sims,.1)) if sims else None,cosine_p90=float(np.quantile(sims,.9)) if sims else None,
            centroid_norm=float(np.linalg.norm(center)),
            rms_standardized_distance=float(np.sqrt(np.mean(np.sum((zs-center)**2,axis=1)))),
            leave_one_out_cosine_mean=float(np.mean(loo)) if loo else None))
    centers=np.array([[r[k+'_z'] for k in ROLE_FEATURES] for r in seasons])
    similarity=[[cosine(a,b) for b in centers] for a in centers]
    return dict(selected=selected,x=x,z=z,scaler=scaler,pca=pca,scores=scores,seasons=seasons,
                stability=stabilities,match_stability=match_stability,similarity=similarity)


def main():
    from src.analysis.team_role_plots import plot_outputs
    import sklearn
    OUT.mkdir(parents=True,exist_ok=True)
    manifest=json.loads(Path('data/processed/manifest.json').read_text())
    data=read_dataset('data/processed');rows=build_rows(data,manifest);result=model_rows(rows)
    selected=result['selected'];seasons=result['seasons'];pca=result['pca'];scaler=result['scaler']
    # Explicit double columns preserve nullable entirely-unavailable features (rather than Arrow null dtype).
    strings={'player_id','player_name','match_id','match_date','opponent_name','home_away','starting_position',
             'nominal_position','formation','minutes_method','exclusion_reason'}
    booleans={'starter','appearance_observed','analysis_eligible'}
    schema=pa.schema([pa.field(k,pa.string() if k in strings else pa.bool_() if k in booleans else pa.float64()) for k in rows[0]])
    pq.write_table(pa.Table.from_pylist(rows,schema=schema),OUT/'player_match_tactical_features.parquet',compression='zstd')
    write_csv(OUT/'player_season_role_vectors.csv',seasons)
    write_csv(OUT/'player_similarity_matrix.csv',[dict(player_id=r['player_id'],player_name=r['player_name'],
        **{other['player_id']:result['similarity'][i][j] for j,other in enumerate(seasons)}) for i,r in enumerate(seasons)])
    windex=next((i for i,r in enumerate(seasons) if r['player_id']==WIRTZ),None)
    if windex is None:raise ValueError('Wirtz does not meet explicit analysis eligibility')
    neighbours=sorted([dict(player_id=r['player_id'],player_name=r['player_name'],cosine_similarity=result['similarity'][windex][i],
        match_count=r['match_count'],represented_minutes=r['represented_minutes']) for i,r in enumerate(seasons)
        if i!=windex and result['similarity'][windex][i] is not None],key=lambda r:(-r['cosine_similarity'],r['player_id']))[:5]
    write_csv(OUT/'wirtz_nearest_roles.csv',neighbours)
    loadings=[]
    for j,key in enumerate(ROLE_FEATURES):
        row=dict(feature=key,group=FEATURE_SPECS[key][0])
        for c in range(len(ROLE_FEATURES)):
            row[f'PC{c+1}_coefficient']=float(pca.components_[c,j])
        row['PC1_correlation']=float(np.corrcoef(result['z'][:,j],result['scores'][:,0])[0,1])
        row['PC2_correlation']=float(np.corrcoef(result['z'][:,j],result['scores'][:,1])[0,1])
        loadings.append(row)
    write_csv(OUT/'pca_loadings.csv',loadings)
    write_csv(OUT/'pca_explained_variance.csv',[dict(component=f'PC{i+1}',explained_variance_ratio=float(v)) for i,v in enumerate(pca.explained_variance_ratio_)])
    write_csv(OUT/'role_stability.csv',result['stability']);write_csv(OUT/'role_stability_by_match.csv',result['match_stability'])
    write_csv(OUT/'pca_player_match_points.csv',[{k:r[k] for k in ('player_id','player_name','match_id','match_date','minutes','nominal_position','starting_position','formation','PC1','PC2')} for r in selected])
    write_csv(OUT/'core_player_role_profiles.csv',[{k:v for k,v in r.items() if k in ('player_id','player_name','match_count','represented_minutes','nominal_positions') or k.endswith('_mean')} for r in seasons])
    write_csv(OUT/'feature_dictionary.csv',[dict(feature=k,group=v[0],unit=v[1],definition=v[2],in_role_vector=True,
        missing_policy='NULL preserved; incomplete rows excluded from model',season_aggregation='match-minute-weighted mean',
        scaler='StandardScaler; eligible match rows; population variance',definition_version='event-mvp-v1 + team-role-v1') for k,v in FEATURE_SPECS.items()])
    corr=np.corrcoef(result['x'],rowvar=False)
    correlations=[dict(feature_a=ROLE_FEATURES[i],feature_b=ROLE_FEATURES[j],pearson_r=float(corr[i,j]))
                  for i in range(len(ROLE_FEATURES)) for j in range(i+1,len(ROLE_FEATURES))]
    write_csv(OUT/'feature_correlations.csv',sorted(correlations,key=lambda r:-abs(r['pearson_r'])))
    plot_outputs(result,neighbours,OUT)
    stable=sorted([r for r in result['stability'] if r['cosine_mean'] is not None],key=lambda r:-r['cosine_mean'])
    variable=sorted(result['stability'],key=lambda r:-r['rms_standardized_distance'])
    def strongest(c):
        order=np.argsort(-np.abs(pca.components_[c]))[:5]
        return ', '.join(f'{ROLE_FEATURES[j]} ({pca.components_[c,j]:+.3f})' for j in order)
    def players_text(rs,key):return '; '.join(f"{r['player_name']} ({r[key]:.3f}; n={r['match_count']})" for r in rs)
    threshold_players={r['player_id'] for r in rows if r['season_known_minutes']>=MIN_SEASON_KNOWN_MINUTES}
    exclusions=Counter(reason.split(':')[0] for r in rows for reason in r['exclusion_reason'].split(';') if reason)
    extreme=np.unravel_index(np.abs(result['z']).argmax(),result['z'].shape)
    summary=f'''# Alonso-Leverkusen Team Tactical Role Space — Milestone 2

## Dataset and selection

StatsBomb Bundesliga 2023/24: {len(data['matches'])} matches, {len(data['events']):,} events. Leverkusen: {len({r['player_id'] for r in rows})} lineup players, {len(rows)} preserved player-match rows; {sum(r['appearance_observed'] for r in rows)} observed appearances. Analysis: {len(selected)} complete player-match vectors, {len(seasons)} players, {sum(r['minutes'] for r in selected):,.2f} represented minutes. Match minimum {MIN_MATCH_MINUTES} known minutes, player season minimum {MIN_SEASON_KNOWN_MINUTES} known minutes. {len(threshold_players)} players satisfy the season threshold before match/completeness filters. Exclusion reasons (overlapping): {dict(exclusions)}. Unused lineup members are retained, not counted as appearances. Goalkeepers remain included and may form a distinct region; these core event features are not a dedicated goalkeeper evaluation.

## Feature representation

{len(ROLE_FEATURES)} features: {', '.join(ROLE_FEATURES)}.

Reuse Milestone 1 definitions. Additional count p90 = raw *90 / known minutes. NULL never becomes zero. xA/dangerous passes/360 context are not implemented. Raw metrics and all short/unknown-minute rows remain in Parquet. Identity/lineup columns are context only. Receptions, carries, shots and touch-proxy counts remain descriptive rather than adding correlated involvement/attacking dimensions. Other lane shares, average reception positions, final-third share and defensive-action sum are likewise excluded from the vector to avoid algebraic or near duplication.

StandardScaler fits ONLY eligible player-match rows (unweighted, mean removal and population standard deviation). Each selected feature has equal standardized weight. Season centroid is the match-minute-weighted mean of standardized match vectors using that SAME scaler; no season refit. Rate means equal summed eligible raw counts *90 / summed eligible minutes. Spatial/ratio means are match-minute-weighted, not pooled event-weighted; this is an intentional representation of typical playing time. Median/std are unweighted match summaries (population std). Full-season known minutes include short matches, but represented minutes and metrics only use eligible matches. Unknown-minute appearances are not silently incorporated in rates.

## PCA

PC1: {pca.explained_variance_ratio_[0]:.2%}; PC2: {pca.explained_variance_ratio_[1]:.2%}; combined: {sum(pca.explained_variance_ratio_[:2]):.2%}. Full SVD PCA is fitted on eligible standardized match rows; player centroids are projected through the same PCA. Coefficients are unit eigenvector weights, not causal effects; feature-PC correlations are separately exported. Axis signs are arbitrary. No semantic axis names are assigned.

PC1 strongest absolute coefficients: {strongest(0)}.

PC2 strongest absolute coefficients: {strongest(1)}.

## Core player observations

Player-specific minute-weighted original-unit feature profiles, median/std and lineup context are exported. The following positions are PC coordinates, not named roles:

''' + '\n'.join(f"- {r['player_name']}: PC1 {r['PC1']:+.3f}, PC2 {r['PC2']:+.3f}, {r['match_count']} matches, {r['represented_minutes']:.2f} represented minutes; nominal positions: {r['nominal_positions']}." for r in seasons) + f'''

## Wirtz nearest observed roles

''' + '\n'.join(f"- {r['player_name']}: cosine {r['cosine_similarity']:.4f}, {r['match_count']} eligible matches." for r in neighbours) + f'''

Cosine uses the full {len(ROLE_FEATURES)}-dimensional standardized season vectors, not the 2D plot. This measures similarity in observed tactical behaviour relative to the team-match reference mean, NOT player ability, recruitment fit or a Wirtz role prototype. Negative values are permitted; no 0–100 score. Near-zero vector norms would yield NULL.

## Role stability and variability

Highest mean match-to-own-season-centroid cosine: {players_text(stable[:3],'cosine_mean')}.

Lowest mean cosine: {players_text(stable[-3:][::-1],'cosine_mean')}.

Largest RMS distance from own centroid in standardized feature space: {players_text(variable[:3],'rms_standardized_distance')}.

Cosine distributions (mean, median, std, p10, p90) and RMS distances are exported. Angular instability and absolute feature variability are different quantities. Own-centroid cosine is descriptive/in-sample and includes each match in its centroid; leave-one-match-out cosine is additionally exported to expose that optimism. No universal high/low stability cutoff is imposed. A centroid near the population mean can have low cosine even without large absolute movement.

## Limitations and diagnostics

One team and season; no causal claims about Alonso instructions. Events measure on-ball activity, not off-ball position or time occupation. Touch proxies can double-count a single possession sequence. All play patterns, including set pieces, remain. Progression uses the local normalized delta-x>=10 rule. Minutes include added time; temporary off-pitch ambiguities remain NULL. Results depend on thresholds, feature selection, scaling and goalkeeper inclusion. Common opponent/game states, home/away and team possession are not adjusted. Match rows are correlated; no held-out predictive evaluation or uncertainty confidence intervals are claimed. StandardScaler preserves sparse-event outliers: max absolute z={abs(result['z'][extreme]):.2f} ({ROLE_FEATURES[extreme[1]]}); feature_correlations.csv exposes residual correlations. No automatic outlier clipping, imputation or tuning to desired neighbours. PCA2 loses {1-sum(pca.explained_variance_ratio_[:2]):.2%} of variance; use full-space cosine for comparisons. Stability estimates depend on sample count and ignore rotation in time. 360 availability does not enter the vector.

## Attribution

{manifest['license_notice']}

Local research outputs only; retain StatsBomb attribution and display its official logo before public publication. No data redistribution performed. Milestone 2 stops here.
'''
    (OUT/'team_role_summary.md').write_text(summary)
    model=dict(scaler='sklearn.preprocessing.StandardScaler',sklearn_version=sklearn.__version__,features=list(ROLE_FEATURES),
        scaler_mean=scaler.mean_.tolist(),scaler_scale=scaler.scale_.tolist(),scaler_variance=scaler.var_.tolist(),
        pca_components=pca.components_.tolist(),pca_mean=pca.mean_.tolist(),explained_variance_ratio=pca.explained_variance_ratio_.tolist(),
        min_match_minutes=MIN_MATCH_MINUTES,min_season_known_minutes=MIN_SEASON_KNOWN_MINUTES,
        fit_rows=len(selected),season_aggregation='match-minute-weighted centroid; unweighted median/std',
        source_version=manifest['source_version'],processed_files=manifest['processed_files'],license_notice=manifest['license_notice'],
        code_sha256={str(p):sha256(p.read_bytes()) for p in [Path(__file__),Path('src/analysis/team_role_plots.py'),Path('src/analysis/wirtz_role_mvp.py')]},
        outputs={p.name:sha256(p.read_bytes()) for p in OUT.iterdir() if p.suffix in ('.csv','.png','.parquet','.md')})
    (OUT/'role_space_manifest.json').write_text(json.dumps(model,indent=2)+'\n')
    print(json.dumps(dict(matches=len(data['matches']),players=len(seasons),raw_rows=len(rows),vectors=len(selected),features=len(ROLE_FEATURES),
        variance=pca.explained_variance_ratio_[:2].tolist(),neighbours=neighbours,stable=stable[:3],variable=variable[:3]),indent=2))

if __name__=='__main__':main()
