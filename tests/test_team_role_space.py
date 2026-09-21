"""Synthetic unit cases only; never mixed into report inputs."""
import unittest
import numpy as np

class TeamRoleTests(unittest.TestCase):
    def test_weighted_centroid_and_zero_norm_cosine(self):
        from src.analysis.team_role_space import weighted_centroid, cosine
        x=np.array([[1.,0.],[3.,2.]])
        np.testing.assert_allclose(weighted_centroid(x,[30,90]),[2.5,1.5])
        self.assertIsNone(cosine([0,0],[1,0]))
        self.assertAlmostEqual(cosine([1,0],[-1,0]),-1)

    def test_filter_boundaries_and_nulls(self):
        from src.analysis.team_role_space import exclusion_reason, ROLE_FEATURES
        r={k:0.1 for k in ROLE_FEATURES};r.update(minutes=30,season_known_minutes=450,events_analysed=10)
        self.assertEqual(exclusion_reason(r),'')
        r['minutes']=None;self.assertIn('unknown_minutes',exclusion_reason(r))
        r['minutes']=29.99;self.assertIn('short_appearance',exclusion_reason(r))
        r['minutes']=30;r['season_known_minutes']=449.9;self.assertIn('season_minutes',exclusion_reason(r))
        r['season_known_minutes']=450;r[ROLE_FEATURES[0]]=None
        self.assertIn('missing_features',exclusion_reason(r))

    def test_extra_rates_preserve_null_and_reuse_raw_qualifiers(self):
        from src.analysis.team_role_space import enrich_metrics
        from src.analysis.wirtz_role_mvp import metrics, creation_metrics
        es=[dict(event_type='SHOT',period=1,source_match_id='1',source_event_id='s',
                 normalized_x=90,normalized_y=50,normalized_end_x=100,normalized_end_y=50,outcome='GOAL')]
        raw={('1','s'):{'shot':{'statsbomb_xg':0.2}}}
        self.assertEqual(creation_metrics(es,raw),dict(shot_assists=0,xg=0.2))
        r=enrich_metrics(metrics(es,None),creation_metrics(es,raw))
        self.assertIsNone(r['xg_p90']);self.assertIsNone(r['forward_pass_rate'])
        r=enrich_metrics(metrics(es,30),creation_metrics(es,raw))
        self.assertAlmostEqual(r['xg_p90'],0.6)

    def test_scaler_uses_only_subset_and_centroids_share_space(self):
        from src.analysis.team_role_space import model_rows, ROLE_FEATURES
        rng=np.random.default_rng(42);rows=[]
        for i in range(24):
            r=dict(zip(ROLE_FEATURES,rng.normal(size=len(ROLE_FEATURES)).tolist()))
            r.update(player_id='a' if i<12 else 'b',player_name='Synthetic A' if i<12 else 'Synthetic B',
                     minutes=30 if i%2 else 90,match_id=str(i),analysis_eligible=True,appearance_observed=True,
                     season_known_minutes=720,nominal_position='Test')
            rows.append(r)
        excluded=dict(rows[0]);excluded.update({k:1e8 for k in ROLE_FEATURES});excluded['analysis_eligible']=False
        rows.append(excluded)
        expected=np.array([[r[k] for k in ROLE_FEATURES] for r in rows[:-1]])
        result=model_rows(rows)
        np.testing.assert_allclose(result['scaler'].mean_,expected.mean(axis=0))
        self.assertIsNone(excluded['PC1'])
        np.testing.assert_allclose(result['similarity'],np.transpose(result['similarity']))
        for s in result['seasons']:
            rs=[r for r in rows if r['analysis_eligible'] and r['player_id']==s['player_id']]
            expected_pc=np.average([[r['PC1'],r['PC2']] for r in rs],axis=0,weights=[r['minutes'] for r in rs])
            np.testing.assert_allclose([s['PC1'],s['PC2']],expected_pc,atol=1e-10)
            expected_rate=sum(r['passes_p90']*r['minutes']/90 for r in rs)*90/sum(r['minutes'] for r in rs)
            self.assertAlmostEqual(s['passes_p90_mean'],expected_rate)
