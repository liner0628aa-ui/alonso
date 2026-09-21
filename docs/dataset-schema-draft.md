# Dataset schema 초안 — Phase 1 검토용

실제 테이블·파이프라인 구현이 아니라 후속 설계 입력이다. 미확보 값은 null과 사유로 보존하며 0으로 채우지 않는다.

| 테이블 / grain | 키 및 핵심 컬럼 | 목적 |
|---|---|---|
| sources / 출처 버전 | source_id, provider, url, retrieved_at_utc, revision, sha256, license_url, license_review_status, redistribution_status, access_method, rate_limit_note | 출처·접근 조건·재현성 |
| entities / 내부 엔티티 | entity_id, entity_type, canonical_name | 선수·팀·감독 이름 충돌 방지 |
| source_entity_map / 소스별 ID | source_id, source_entity_id, entity_id, mapping_method, confidence | Wirtz/Palmer 교차 소스 식별 |
| availability / 선수×팀×시즌×소스×grain×feature group | entity_id, team_id, competition_id, season_id, source_id, grain, level, status, expected_matches, available_matches, verified_matches, minutes, evidence_url, checked_at, limitation | 시즌·선수·해상도별 실제 확보 상태 |
| manager_stints / 팀×감독 기간 | stint_id, team_id, manager_id, valid_from, valid_to_exclusive, evidence_url, verified | 감독 경계 검증; 추측으로 채우지 않음 |
| matches / 경기 | match_id, source_match_id, source_id, competition_id, season_id, date, home_team_id, away_team_id, home_manager_id, away_manager_id, event_status, status_360 | 실제 경기별 감독 우선 |
| player_appearances / 선수×경기×팀 | match_id, player_id, team_id, minutes, starter, nominal_position, stint_id, source_id | 분모와 split group |
| role_intervals / 선수×경기×역할 구간 | match_id, player_id, start_second, end_second, role_label, formation, evidence, confidence | 포지션 변화; 실제 근거 있을 때만 |
| events / 소스 이벤트 | source_id, match_id, event_id, index, period, timestamp, player_id, team_id, possession_id, type, x, y, end_x, end_y, outcome, under_pressure, related_event_ids, raw_qualifiers | 좌표 없는 이벤트 허용; period별 정렬 |
| frames_360 / 이벤트별 frame | source_id, match_id, event_id, visible_area, frame_available | UUID로 event 연결 |
| frame_players / frame 안 관측 인물 | source_id, match_id, event_id, observation_index, x, y, teammate, actor, keeper | observation_index는 실제 선수 ID 아님 |
| aggregate_observations / 선수×기간×metric | player_id, team_id, competition_id, season_id, stint_id_nullable, period_start, period_end, grain, source_id, metric_id, raw_value, minutes, denominator_value | 시즌 합을 임의 감독별로 분배하지 않음 |
| feature_registry / feature 버전 | metric_id, definition_version, category, level, unit, formula, numerator, denominator, coordinate_system, source_equivalence, requires_tracking | provider 정의 차이 관리 |
| feature_values / 관측 단위×feature | observation_id, metric_id, value, measurement_type, missing_reason, source_id, coverage, imputed, transform_version | observed/derived/coarse_proxy/unavailable 구분 |
| contexts / 경기×팀 또는 기간×팀 | observation_id, possession_pct, team_passes, attacking_strength, score_state, home_away, tempo, block_height_proxy, definition_version | grain 다른 context 자동 혼합 금지 |
| cohorts / 분석 풀 구성원 | cohort_id, observation_id, inclusion_reason, excluded_reason, min_minutes, role_rule, source_policy | 비교군·선수 수·표본 편향 기록 |
| model_runs / 실행 | run_id, cohort_id, seed, split_manifest, train_fit_ids, feature_set, scaler, checkpoint, code_revision, metrics | 후속 단계용; 현재 모델 없음 |

권장 `availability.status`: verified_metadata / verified_content / unverified / unavailable_confirmed / access_failed. 네트워크 실패는 unavailable_confirmed가 아니다.

권장 `missing_reason`: source_not_provided / not_collected / outside_visible_area / insufficient_minutes / definition_incompatible / access_failed / not_applicable.

핵심 무결성 규칙:

1. 같은 제공자·정의 버전의 metric만 직접 합산한다. 선수 이름을 join key로 사용하지 않는다.
2. event와 360은 match+event UUID로 결합하고 결합률을 기록한다. 모든 이벤트에 frame이 있다는 가정은 금지한다.
3. 좌표계의 축·방향·원점·pitch 크기를 명시한 후 정규화한다. 이미 공격 방향이 정규화된 소스에 다시 전후반 flip을 적용하지 않는다.
4. thirds와 penalty area를 별도 속성으로 저장해 중복 카운트를 막는다. coarse third 집계로 5-lane 좌표를 생성하지 않는다.
5. count per90의 minutes는 해당 팀·기간과 일치해야 한다. 0분이면 per90은 null이다.
6. season-manager split은 실제 경기 또는 제공된 기간별 집계가 있을 때만 생성한다. 알 수 없는 감독 값은 null이다.
7. source availability/missing mask는 학습 입력에서 역할 정보처럼 사용하지 않는다. 교차 출처 혼합이 불가피하면 source별 민감도 검증이 필수다.
8. 무관측 metric의 cosine, category score, fit score는 N/A. 집계만 있는 Palmer에게 spatial heatmap을 생성하지 않고 실제 zone 비중 chart에 coarse aggregate 라벨을 단다.
9. 모델용 split과 scaler/imputation fit ID를 저장해 같은 경기·선수의 누수를 평가 설계에 따라 점검한다.
10. 전역 seed 후보는 42로 하나만 관리하며 실제 코드 상수 생성은 후속 구현 범위다.
