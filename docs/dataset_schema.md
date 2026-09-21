> Historical Phase 2 contract, still reused by ingestion. For current Milestone 1 outputs and explicitly separate proxy definitions see [tactical_features_mvp.md](tactical_features_mvp.md). Candidate registry entries below do not imply implemented features.

# Phase 2 — Dataset schema v2.0.1

이 문서는 Phase 1 초안을 구체화한 현재 계약이다. 구현 범위는 dataclass 검증, 좌표 변환, zone 규칙, 공통 숫자 행렬 추출 및 synthetic 테스트다. 모델·ingestion·대량 다운로드·Streamlit은 없다. Python 3.11+ 문법 및 표준 라이브러리만 사용했으며 실제 테스트 환경은 Python 3.13.5다.

## 근거와 가용성

Phase 1에서 실제 확보한 것은 StatsBomb 레버쿠젠 2023/24 34경기 메타데이터와 한 경기 라인업이다. 출전시간·event feature 값은 아직 실측하지 않았다. 따라서 feature registry의 candidate는 확보 완료가 아니다. FBref의 현재 advanced 제공 및 약관은 미확인이다. Palmer synthetic 행은 스키마 표현 능력만 검증하며 실제 데이터 가용성을 증명하지 않는다.

## 계층과 분석 단위

`raw_events(payload 원문) → normalized_events(이벤트당 행) → player_match_features(선수×경기당 행) → role_feature_vector(명시적으로 선택한 수치 컬럼) → ML embedding(미구현)`

raw 계층은 공급자 JSON을 payload에 그대로 보존한다. raw에 canonical 이름으로 원본을 덮어쓰지 않는다. 별도 normalized event에서 공급자별 mapping을 적용할 수 있도록 계약만 제공한다. coordinate transform은 순수 함수이며 event adapter는 아직 없다.

player_match_features의 PK는 `(player_id, match_id)`다. ID는 내부 canonical ID이고, source-native ID는 문자열로 별도 보존한다. 다른 공급자의 동일 경기·선수는 source ID mapping으로 동일 canonical ID에 연결한 뒤 중복 충돌을 해결한다. 이름을 join key로 쓰지 않는다. 하나의 feature 행은 하나의 data_source를 기본으로 하며 다중 소스 enrichment는 provenance 구조 확장 전 금지한다.

기본 feature registry는 A~I 전체 컬럼을 동일 순서로 보유한다. Python에서는 features dict로 저장하지만 논리적으로 wide table의 컬럼이다. feature_status/missing_reasons/definition_ids는 같은 키를 갖는 필수 병렬 metadata map이다. 모든 feature 키가 필요하지만 값은 null 가능하다. 미지원 feature를 제거하여 두 선수의 벡터 길이를 다르게 만들지 않는다.

player-season / player-manager-period / player-90-minutes-window는 PeriodAggregate 별도 테이블이다. season aggregate에 match_id를 발명하지 않는다. 경기별 aggregate를 확보하면 event 없이도 PlayerMatch를 사용한다. 시즌 자료만 있으면 PeriodAggregate에 저장하고 player-match 모델에 입력할 수 없다. 파생 집계는 raw count와 minutes를 합쳐 per90을 다시 계산한다. 개별 per90의 단순 평균은 금지한다. rolling window는 실제 출전시간 축의 연속 90분이며 match interval lineage가 필요하다. 현재 생성 코드는 없고 contributing_match_ids를 보존하는 계약만 제공한다. 겹치는 window는 같은 원본 경기를 공유하므로 분할 경계를 넘어 사용하지 않는다.

## 컬럼 표 읽는 법

required=Y는 생성 시 인자가 필수인 식별자 또는 항상 존재해야 하는 feature 키다. required=N은 기본값으로 생성되는 컬럼이며 저장 시에도 보존한다. nullable은 값의 null 허용 여부다. source_or_derived는 공급자 집계 또는 검증된 자체 집계이며, `_raw`는 **비정규화 수치**라는 뜻이지 JSON raw 계층이라는 뜻이 아니다. 본문 표의 expected source는 입수 확정이 아니라 계약상의 입력 경로다.

## RawEvent 컬럼

| column name | dtype | unit | description | raw / derived | nullable | required | expected source |
|---|---|---|---|---|---|---|---|
| data_source | str | — | 출처/버전 manifest 참조 키; synthetic는 실제 자료 아님 | raw | N | Y | 원제공자 JSON |
| source_match_id | str | — | 문자열로 보존한 원제공자 경기 ID | raw | N | Y | 원제공자 JSON |
| source_event_id | str | — | 원제공자 이벤트 ID | raw | N | Y | 원제공자 JSON |
| payload | dict | — | 필드 손실 없이 보존하는 원본 JSON object | raw | N | Y | 원제공자 JSON |

## NormalizedEvent 컬럼

| column name | dtype | unit | description | raw / derived | nullable | required | expected source |
|---|---|---|---|---|---|---|---|
| match_id | str | — | 공급자 간 연결된 내부 경기 ID | normalized metadata | N | Y | StatsBomb JSON / 허용된 aggregate |
| event_id | str | — | canonical 이벤트 ID | normalized metadata | N | Y | StatsBomb JSON / 허용된 aggregate |
| data_source | str | — | 출처/버전 manifest 참조 키; synthetic는 실제 자료 아님 | normalized metadata | N | Y | StatsBomb JSON / 허용된 aggregate |
| source_match_id | str | — | 문자열로 보존한 원제공자 경기 ID | raw | N | Y | StatsBomb JSON / 허용된 aggregate |
| source_event_id | str | — | 원제공자 이벤트 ID | raw | N | Y | StatsBomb JSON / 허용된 aggregate |
| event_index | int | — | 원본 이벤트 순번; timestamp 동률 처리 | normalized metadata | N | Y | StatsBomb JSON / 허용된 aggregate |
| period | int | — | 1/2 정규, 3/4 연장, 5 승부차기; 5는 역할집계 제외 | normalized metadata | N | Y | StatsBomb JSON / 허용된 aggregate |
| minute | int | — | 원본 경기 minute 정수; period/index와 함께 순서 결정 | normalized metadata | N | Y | StatsBomb JSON / 허용된 aggregate |
| second | float | second | minute 안 초; 0 이상 60 미만 | normalized metadata | N | Y | StatsBomb JSON / 허용된 aggregate |
| event_type | str | — | canonical 이벤트 종류; 공급자 전용 qualifier는 raw payload 보존 | normalized metadata | N | Y | StatsBomb JSON / 허용된 aggregate |
| player_id | str / None | — | 내부 선수 ID; 이름 대신 사용 | normalized metadata | Y | N | StatsBomb JSON / 허용된 aggregate |
| team_id | str / None | — | 내부 소속 팀 ID | normalized metadata | Y | N | StatsBomb JSON / 허용된 aggregate |
| source_player_id | str / None | — | 원제공자 선수 ID; 미제공 시 period에서는 null | raw | Y | N | StatsBomb JSON / 허용된 aggregate |
| source_team_id | str / None | — | 원제공자 팀 ID | raw | Y | N | StatsBomb JSON / 허용된 aggregate |
| source_x | float / None | source unit | 변환 전 x; 원본 범위는 transform metadata에 보존 | raw | Y | N | StatsBomb JSON / 허용된 aggregate |
| source_y | float / None | source unit | 변환 전 y; 원본 범위는 transform metadata에 보존 | raw | Y | N | StatsBomb JSON / 허용된 aggregate |
| source_end_x | float / None | source unit | 변환 전 end_x; 원본 범위는 transform metadata에 보존 | raw | Y | N | StatsBomb JSON / 허용된 aggregate |
| source_end_y | float / None | source unit | 변환 전 end_y; 원본 범위는 transform metadata에 보존 | raw | Y | N | StatsBomb JSON / 허용된 aggregate |
| normalized_x | float / None | 0–100 | 0–100 공격 방향 통일 x; 좌표 쌍으로 null 처리 | derived | Y | N | StatsBomb JSON / 허용된 aggregate |
| normalized_y | float / None | 0–100 | 0–100 공격 방향 통일 y; 좌표 쌍으로 null 처리 | derived | Y | N | StatsBomb JSON / 허용된 aggregate |
| normalized_end_x | float / None | 0–100 | 0–100 공격 방향 통일 end_x; 좌표 쌍으로 null 처리 | derived | Y | N | StatsBomb JSON / 허용된 aggregate |
| normalized_end_y | float / None | 0–100 | 0–100 공격 방향 통일 end_y; 좌표 쌍으로 null 처리 | derived | Y | N | StatsBomb JSON / 허용된 aggregate |
| outcome | str / None | — | 종류별 canonical 결과; 필드 부재를 성공으로 일반화 금지 | normalized metadata | Y | N | StatsBomb JSON / 허용된 aggregate |
| body_part | str / None | — | canonical 신체 부위; 해당 없으면 null | normalized metadata | Y | N | StatsBomb JSON / 허용된 aggregate |
| under_pressure | bool / None | — | 압박 여부; 공급자 누락 의미 확인 전 false 대체 금지 | normalized metadata | Y | N | StatsBomb JSON / 허용된 aggregate |
| possession_id | str / None | — | source-match 범위 possession ID를 문자열로 보존 | normalized metadata | Y | N | StatsBomb JSON / 허용된 aggregate |
| play_pattern | str / None | — | 공격 패턴 label; 공급자 정의 버전 필요 | normalized metadata | Y | N | StatsBomb JSON / 허용된 aggregate |
| coordinate_transform | str / None | — | 좌표 크기·원점·공격방향·변환 버전 식별자 | normalized metadata | Y | N | 검증된 registry; 미확인 시 null |

## PlayerMatch 컬럼

| column name | dtype | unit | description | raw / derived | nullable | required | expected source |
|---|---|---|---|---|---|---|---|
| player_id | str | — | 내부 선수 ID; 이름 대신 사용 | normalized metadata | N | Y | StatsBomb JSON / 허용된 aggregate |
| player_name | str | — | 표시용 선수 이름 | normalized metadata | N | Y | StatsBomb JSON / 허용된 aggregate |
| team_id | str | — | 내부 소속 팀 ID | normalized metadata | N | Y | StatsBomb JSON / 허용된 aggregate |
| team_name | str | — | 표시용 팀 이름 | normalized metadata | N | Y | StatsBomb JSON / 허용된 aggregate |
| opponent_id | str | — | 내부 상대 팀 ID | normalized metadata | N | Y | StatsBomb JSON / 허용된 aggregate |
| opponent_name | str | — | 표시용 상대 이름 | normalized metadata | N | Y | StatsBomb JSON / 허용된 aggregate |
| match_id | str | — | 공급자 간 연결된 내부 경기 ID | normalized metadata | N | Y | StatsBomb JSON / 허용된 aggregate |
| competition | str | — | 대회 canonical label; 시즌 키에 포함 | normalized metadata | N | Y | StatsBomb JSON / 허용된 aggregate |
| season | str | — | 시즌 canonical label 예: 2023/2024 | normalized metadata | N | Y | StatsBomb JSON / 허용된 aggregate |
| match_date | str | — | ISO 경기 날짜 | normalized metadata | N | Y | StatsBomb JSON / 허용된 aggregate |
| data_source | str | — | 출처/버전 manifest 참조 키; synthetic는 실제 자료 아님 | normalized metadata | N | Y | StatsBomb JSON / 허용된 aggregate |
| source_match_id | str | — | 문자열로 보존한 원제공자 경기 ID | raw | N | Y | StatsBomb JSON / 허용된 aggregate |
| source_player_id | str | — | 원제공자 선수 ID; 미제공 시 period에서는 null | raw | N | Y | StatsBomb JSON / 허용된 aggregate |
| minutes_played | float / None | minute | 해당 선수의 실제 출전 분; 추가시간 포함한 공급자 규약 기록; 모르면 null | normalized metadata | Y | Y | StatsBomb JSON / 허용된 aggregate |
| home_away | str | — | fixture 기준 home 또는 away; 중립 경기에도 지정 홈/원정 | normalized metadata | N | Y | StatsBomb JSON / 허용된 aggregate |
| event_data_available | bool | — | 해당 선수/경기 event 내용을 확보·검증했는지 | normalized metadata | N | N | StatsBomb JSON / 허용된 aggregate |
| spatial_data_available | bool | — | 사용 가능한 event 좌표 존재 여부; 360 존재와 별개 | normalized metadata | N | N | StatsBomb JSON / 허용된 aggregate |
| manager_id | str / None | — | 검증된 내부 감독 ID | normalized metadata | Y | N | StatsBomb JSON / 허용된 aggregate |
| manager | str / None | — | 감독 표시명 | normalized metadata | Y | N | StatsBomb JSON / 허용된 aggregate |
| manager_period | str / None | — | 검증된 팀-감독 stint ID; 날짜는 외부 stint metadata 참조 | normalized metadata | Y | N | 검증된 registry; 미확인 시 null |
| nominal_position | str / None | — | 출처가 명시한 해당 경기 역할; season position을 무표시 전용 금지 | normalized metadata | Y | N | StatsBomb JSON / 허용된 aggregate |
| starting_position | str / None | — | 선발 당시 위치; 교체 선수는 null | normalized metadata | Y | N | StatsBomb JSON / 허용된 aggregate |
| formation | str / None | — | 선수 출전 시작 시 팀 포메이션; 변경 구간은 후속 role interval 테이블 | normalized metadata | Y | N | StatsBomb JSON / 허용된 aggregate |
| source_team_id | str / None | — | 원제공자 팀 ID | raw | Y | N | StatsBomb JSON / 허용된 aggregate |
| source_opponent_id | str / None | — | 원제공자 상대 팀 ID | raw | Y | N | StatsBomb JSON / 허용된 aggregate |
| features | dict | — | 전체 canonical registry와 일치하는 수치/null map | derived | N | N | StatsBomb JSON / 허용된 aggregate |
| feature_status | dict | — | feature별 observed / derived / coarse_proxy / unavailable | derived | N | N | StatsBomb JSON / 허용된 aggregate |
| missing_reasons | dict | — | null 사유; 관측값이 있으면 null | derived | N | N | StatsBomb JSON / 허용된 aggregate |
| definition_ids | dict | — | feature별 제공자·정의·단위·버전의 승인된 식별자; 수치가 있으면 필수 | derived | N | N | 검증된 registry; 미확인 시 null |

## PeriodAggregate 컬럼

| column name | dtype | unit | description | raw / derived | nullable | required | expected source |
|---|---|---|---|---|---|---|---|
| player_id | str | — | 내부 선수 ID; 이름 대신 사용 | normalized metadata | N | Y | StatsBomb JSON / 허용된 aggregate |
| team_id | str | — | 내부 소속 팀 ID | normalized metadata | N | Y | StatsBomb JSON / 허용된 aggregate |
| competition | str | — | 대회 canonical label; 시즌 키에 포함 | normalized metadata | N | Y | StatsBomb JSON / 허용된 aggregate |
| season | str | — | 시즌 canonical label 예: 2023/2024 | normalized metadata | N | Y | StatsBomb JSON / 허용된 aggregate |
| grain | str | — | player-season / player-manager-period / player-90-minutes-window | normalized metadata | N | Y | StatsBomb JSON / 허용된 aggregate |
| period_start | str | — | ISO 기간 시작일, 포함 | normalized metadata | N | Y | StatsBomb JSON / 허용된 aggregate |
| period_end | str | — | ISO 기간 종료일, 포함 | normalized metadata | N | Y | StatsBomb JSON / 허용된 aggregate |
| data_source | str | — | 출처/버전 manifest 참조 키; synthetic는 실제 자료 아님 | normalized metadata | N | Y | StatsBomb JSON / 허용된 aggregate |
| minutes_played | float / None | minute | 해당 선수의 실제 출전 분; 추가시간 포함한 공급자 규약 기록; 모르면 null | normalized metadata | Y | Y | StatsBomb JSON / 허용된 aggregate |
| manager_period | str / None | — | 검증된 팀-감독 stint ID; 날짜는 외부 stint metadata 참조 | normalized metadata | Y | N | 검증된 registry; 미확인 시 null |
| features | dict | — | 전체 canonical registry와 일치하는 수치/null map | derived | N | N | StatsBomb JSON / 허용된 aggregate |
| feature_status | dict | — | feature별 observed / derived / coarse_proxy / unavailable | derived | N | N | StatsBomb JSON / 허용된 aggregate |
| missing_reasons | dict | — | null 사유; 관측값이 있으면 null | derived | N | N | StatsBomb JSON / 허용된 aggregate |
| definition_ids | dict | — | feature별 제공자·정의·단위·버전의 승인된 식별자; 수치가 있으면 필수 | derived | N | N | 검증된 registry; 미확인 시 null |
| source_player_id | str / None | — | 원제공자 선수 ID; 미제공 시 period에서는 null | raw | Y | N | StatsBomb JSON / 허용된 aggregate |
| source_period_id | str / None | — | 원제공자 기간 row ID; 없으면 null | raw | Y | N | StatsBomb JSON / 허용된 aggregate |
| contributing_match_ids | tuple | — | 파생 aggregate 원본 경기 ID tuple; 외부 시즌 합계는 빈 tuple, 개별 경기 존재를 주장하지 않음 | normalized metadata | N | N | StatsBomb JSON / 허용된 aggregate |

## 계산형 metadata 컬럼

| column name | dtype | unit | description | raw / derived | nullable | required | expected source |
|---|---|---|---|---|---|---|---|
| player_season_id | tuple[str,str,str] | key | player_id, competition, season; 직렬화는 JSON array | derived | N | Y | canonical IDs |
| team_season_id | tuple[str,str,str] | key | team_id, competition, season | derived | N | Y | canonical IDs |
| missing_feature_count | int | features | 전체 registry null 수; ML 선택 subset 결측 수와 다름 | derived | N | Y | features |
| data_quality_flag | tuple[str] | flags | partial_features / unknown_minutes / zero_minutes / aggregate_only | derived | N | Y | row metadata |

20분 행은 minutes_played=20으로 보존한다. quality flag 자체가 표본 크기 충분성을 보장하지 않는다. numeric_matrix의 min_minutes 인자를 명시해 필터 기준을 적용하며 미달 행은 조용히 제외하지 않고 오류를 낸다. 0분·출전 분 미상은 학습 입력에서 차단한다. 최소 출전시간의 최적 기준은 이번 단계에서 임의 확정하지 않는다.

## Player-match 및 period feature 컬럼 전체

모든 feature는 null 가능하고 키는 필수다. count는 raw int, p90 float다. xG/xA와 거리 누계는 연속형이며 raw/p90를 같이 보존한다. 거리 단위 pitch_units는 0–100 좌표의 Euclidean 길이로 미터가 아니다. 실제 미터 기반 공급자 거리를 그대로 여기에 넣을 수 없으며 정의 호환성 검증이 필요하다.

| column name | dtype | unit | description | raw / derived | nullable | required | expected source |
|---|---|---|---|---|---|---|---|
| touches_raw | int | count | 공급자 정의의 볼 터치; 이벤트 합으로 대체 금지 | source_or_derived | Y | Y | 미확보; 정의 검증 전 unavailable |
| touches_p90 | float | count/90min | 공급자 정의의 볼 터치; 이벤트 합으로 대체 금지의 90분당 값 | derived | Y | Y | 미확보; 정의 검증 전 unavailable |
| receptions_raw | int | count | 명시적 수신 이벤트 | source_or_derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| receptions_p90 | float | count/90min | 명시적 수신 이벤트의 90분당 값 | derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| passes_attempted_raw | int | count | 패스 시도 | source_or_derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| passes_attempted_p90 | float | count/90min | 패스 시도의 90분당 값 | derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| passes_completed_raw | int | count | 완료 패스 | source_or_derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| passes_completed_p90 | float | count/90min | 완료 패스의 90분당 값 | derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| progressive_passes_raw | int | count | 정의 버전 확정이 필요한 전진 패스 | source_or_derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| progressive_passes_p90 | float | count/90min | 정의 버전 확정이 필요한 전진 패스의 90분당 값 | derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| progressive_carries_raw | int | count | 정의 버전 확정이 필요한 전진 운반 | source_or_derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| progressive_carries_p90 | float | count/90min | 정의 버전 확정이 필요한 전진 운반의 90분당 값 | derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| final_third_entries_raw | int | count | 패스+캐리 진입; 중복 제거 규약 필요 | source_or_derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| final_third_entries_p90 | float | count/90min | 패스+캐리 진입; 중복 제거 규약 필요의 90분당 값 | derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| carries_into_final_third_raw | int | count | final third 밖에서 안으로 캐리 | source_or_derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| carries_into_final_third_p90 | float | count/90min | final third 밖에서 안으로 캐리의 90분당 값 | derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| carries_into_penalty_area_raw | int | count | 박스 밖에서 안으로 캐리 | source_or_derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| carries_into_penalty_area_p90 | float | count/90min | 박스 밖에서 안으로 캐리의 90분당 값 | derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| passes_into_final_third_raw | int | count | final third 밖에서 안으로 완료 패스 | source_or_derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| passes_into_final_third_p90 | float | count/90min | final third 밖에서 안으로 완료 패스의 90분당 값 | derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| passes_into_penalty_area_raw | int | count | 박스 밖에서 안으로 완료 패스 | source_or_derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| passes_into_penalty_area_p90 | float | count/90min | 박스 밖에서 안으로 완료 패스의 90분당 값 | derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| key_passes_raw | int | count | 슈팅 연결 패스; shot assist와 중복 가능 | source_or_derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| key_passes_p90 | float | count/90min | 슈팅 연결 패스; shot assist와 중복 가능의 90분당 값 | derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| shot_assists_raw | int | count | 슈팅 어시스트; 연결 ID 검증 필요 | source_or_derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| shot_assists_p90 | float | count/90min | 슈팅 어시스트; 연결 ID 검증 필요의 90분당 값 | derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| through_balls_raw | int | count | 공급자 through-ball qualifier | source_or_derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| through_balls_p90 | float | count/90min | 공급자 through-ball qualifier의 90분당 값 | derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| xA_raw | float | expected_goals | expected assists; shot xG 합계와 동일시 금지 | source_or_derived | Y | Y | 미확보; 정의 검증 전 unavailable |
| xA_p90 | float | expected_goals/90min | expected assists; shot xG 합계와 동일시 금지의 90분당 값 | derived | Y | Y | 미확보; 정의 검증 전 unavailable |
| shot_creating_actions_raw | int | count | 공급자 SCA 정의 확인 필요 | source_or_derived | Y | Y | 미확보; 정의 검증 전 unavailable |
| shot_creating_actions_p90 | float | count/90min | 공급자 SCA 정의 확인 필요의 90분당 값 | derived | Y | Y | 미확보; 정의 검증 전 unavailable |
| goal_creating_actions_raw | int | count | 공급자 GCA 정의 확인 필요 | source_or_derived | Y | Y | 미확보; 정의 검증 전 unavailable |
| goal_creating_actions_p90 | float | count/90min | 공급자 GCA 정의 확인 필요의 90분당 값 | derived | Y | Y | 미확보; 정의 검증 전 unavailable |
| shots_raw | int | count | 승부차기 제외 슈팅 | source_or_derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| shots_p90 | float | count/90min | 승부차기 제외 슈팅의 90분당 값 | derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| shots_on_target_raw | int | count | 결과 taxonomy 검증한 유효슈팅 | source_or_derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| shots_on_target_p90 | float | count/90min | 결과 taxonomy 검증한 유효슈팅의 90분당 값 | derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| xG_raw | float | expected_goals | 제공자 expected goals 합 | source_or_derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| xG_p90 | float | expected_goals/90min | 제공자 expected goals 합의 90분당 값 | derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| non_penalty_xG_raw | float | expected_goals | 페널티 제외 xG | source_or_derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| non_penalty_xG_p90 | float | expected_goals/90min | 페널티 제외 xG의 90분당 값 | derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| box_touches_raw | int | count | 박스 안 공급자 정의 터치 | source_or_derived | Y | Y | 미확보; 정의 검증 전 unavailable |
| box_touches_p90 | float | count/90min | 박스 안 공급자 정의 터치의 90분당 값 | derived | Y | Y | 미확보; 정의 검증 전 unavailable |
| penalty_area_receptions_raw | int | count | 공격 박스 안 수신 | source_or_derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| penalty_area_receptions_p90 | float | count/90min | 공격 박스 안 수신의 90분당 값 | derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| carries_raw | int | count | 볼 운반 이벤트 | source_or_derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| carries_p90 | float | count/90min | 볼 운반 이벤트의 90분당 값 | derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| carry_distance_raw | float | pitch_units | 좌표 기반 볼 운반 누적 거리 | source_or_derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| carry_distance_p90 | float | pitch_units/90min | 좌표 기반 볼 운반 누적 거리의 90분당 값 | derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| progressive_carry_distance_raw | float | pitch_units | 정의 승인된 전진 운반 거리 | source_or_derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| progressive_carry_distance_p90 | float | pitch_units/90min | 정의 승인된 전진 운반 거리의 90분당 값 | derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| take_ons_attempted_raw | int | count | 상대 돌파 시도 | source_or_derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| take_ons_attempted_p90 | float | count/90min | 상대 돌파 시도의 90분당 값 | derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| take_ons_completed_raw | int | count | 성공 돌파 | source_or_derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| take_ons_completed_p90 | float | count/90min | 성공 돌파의 90분당 값 | derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| dispossessions_raw | int | count | 공급자 dispossession 이벤트 | source_or_derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| dispossessions_p90 | float | count/90min | 공급자 dispossession 이벤트의 90분당 값 | derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| miscontrols_raw | int | count | 볼 컨트롤 실패 | source_or_derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| miscontrols_p90 | float | count/90min | 볼 컨트롤 실패의 90분당 값 | derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| turnovers_raw | int | count | 중복 없이 정의한 소유 상실; 현재 정의 미확정 | source_or_derived | Y | Y | 미확보; 정의 검증 전 unavailable |
| turnovers_p90 | float | count/90min | 중복 없이 정의한 소유 상실; 현재 정의 미확정의 90분당 값 | derived | Y | Y | 미확보; 정의 검증 전 unavailable |
| pressures_raw | int | count | pressure 이벤트 | source_or_derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| pressures_p90 | float | count/90min | pressure 이벤트의 90분당 값 | derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| successful_pressures_raw | int | count | 성공 압박의 시간/소유 회복 정의 미확정 | source_or_derived | Y | Y | 미확보; 정의 검증 전 unavailable |
| successful_pressures_p90 | float | count/90min | 성공 압박의 시간/소유 회복 정의 미확정의 90분당 값 | derived | Y | Y | 미확보; 정의 검증 전 unavailable |
| tackles_raw | int | count | 태클 유형 duel | source_or_derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| tackles_p90 | float | count/90min | 태클 유형 duel의 90분당 값 | derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| interceptions_raw | int | count | 가로채기 정의 및 성공 결과 검증 필요 | source_or_derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| interceptions_p90 | float | count/90min | 가로채기 정의 및 성공 결과 검증 필요의 90분당 값 | derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| recoveries_raw | int | count | 볼 회수 이벤트 | source_or_derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| recoveries_p90 | float | count/90min | 볼 회수 이벤트의 90분당 값 | derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| avg_reception_x | float | normalized_coordinate | 수신 x 평균 | source_or_derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| avg_reception_y | float | normalized_coordinate | 수신 y 평균 | source_or_derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| avg_touch_x | float | normalized_coordinate | 터치 정의에 따른 x 평균, 경기 전체 평균 위치 아님 | source_or_derived | Y | Y | 미확보; 정의 검증 전 unavailable |
| avg_touch_y | float | normalized_coordinate | 터치 정의에 따른 y 평균 | source_or_derived | Y | Y | 미확보; 정의 검증 전 unavailable |
| box_touch_share | float | share | 공격 박스 터치 비중; 실제 coarse aggregate 허용 | source_or_derived | Y | Y | 미확보; 정의 검증 전 unavailable |
| central_touch_share | float | share | 중앙 터치 / 좌표 관측 터치 | source_or_derived | Y | Y | 미확보; 정의 검증 전 unavailable |
| final_third_touch_share | float | share | final third 터치 비중; 실제 coarse aggregate 허용 | source_or_derived | Y | Y | 미확보; 정의 검증 전 unavailable |
| left_halfspace_touch_share | float | share | 좌 half-space 터치 / 좌표 관측 터치 | source_or_derived | Y | Y | 미확보; 정의 검증 전 unavailable |
| match_tempo_proxy | float | events/minute | 정의된 eligible event / 명시된 match minutes; 아직 정의 미확정 | source_or_derived | Y | Y | 미확보; 정의 검증 전 unavailable |
| opponent_possession | float | share | 같은 정의의 상대 점유 비율 | source_or_derived | Y | Y | 미확보; 정의 검증 전 unavailable |
| pass_completion | float | share | passes_completed / passes_attempted; 0회 시 null | source_or_derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| right_halfspace_touch_share | float | share | 우 half-space 터치 / 좌표 관측 터치 | source_or_derived | Y | Y | 미확보; 정의 검증 전 unavailable |
| score_state_minutes_drawing | float | minutes | 선수 출전 중 동점 시간 | source_or_derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| score_state_minutes_losing | float | minutes | 선수 출전 중 열세 시간 | source_or_derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| score_state_minutes_winning | float | minutes | 선수 출전 중 리드 시간 | source_or_derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| team_pass_volume | int | count | 경기 전체 팀 패스 시도 수, 선수 출전 구간 분모와 구분 | source_or_derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| team_possession | float | share | 동일 경기 공식 팀 점유 비율; possession ID 비율과 다름 | source_or_derived | Y | Y | 미확보; 정의 검증 전 unavailable |
| team_shots | int | count | 경기 전체 팀 슈팅 수 | source_or_derived | Y | Y | StatsBomb event 후보 / 동일 정의의 허용된 aggregate; 본문 미검증 |
| wing_touch_share | float | share | 좌우 wing 터치 합 / 좌표 관측 터치 | source_or_derived | Y | Y | 미확보; 정의 검증 전 unavailable |

## 공급자 mapping 계약 (adapter는 미구현)

| canonical | StatsBomb 후보 경로 | 현재 검증 상태 |
|---|---|---|
| match_id / source_match_id | 경기 목록 match_id → 내부 ID mapping / 문자열 원본 | Phase 1 확인 |
| player_id / source_player_id | lineup player_id → 내부 ID mapping / 문자열 원본 | 표본 lineup 확인 |
| team / opponent / manager | home_team / away_team 및 managers | 경기 목록 확인 |
| event_id / event_index / event_type | id / index / type.name | event 본문 미검증 |
| source_x, source_y | location[0:2] | event 본문 미검증 |
| source_end_x, source_end_y | pass.end_location / carry.end_location / shot.end_location 앞 2축 | event 본문 미검증; shot z는 raw 보존 |
| minute / second / period | minute / second / period | event 본문 미검증 |
| outcome / body_part | event type별 nested qualifier | event 본문 미검증; 누락 의미는 종류별 처리 |
| possession_id / play_pattern | possession / play_pattern.name | event 본문 미검증 |
| under_pressure | under_pressure | 미검증; absent→false는 정의 확인 후만 |
| minutes / starting_position / formation | lineup intervals / Starting XI tactics / 교체·퇴장 시간 | 실제 내용·규약 미검증 |

Palmer 공급자 column mapping은 아직 확정할 수 없다. 합법적으로 확보한 경기 집계만 canonical feature 이름에 mapping한다. StatsBomb만의 nested key는 raw와 adapter 경계에 머물고 numeric_matrix는 ML_FEATURE_COLUMNS에 없는 key를 거절한다. FEATURES의 context 컬럼도 역할 입력에서는 제외한다.

## 좌표와 tactical zones (README 역할의 경계 설명)

요청한 여섯 파일 범위를 지키기 위해 기존 Phase 1 README는 수정하지 않았으며 경계 설명을 이 문서에 둔다. 단일 정의 위치는 src/config/pitch_zones.py다.

- 표준 좌표 x,y ∈ [0,100], 항상 공격 left→right. y=0은 정규화된 공격자의 왼쪽이다.
- 원점 top 기준 `nx=100*x/width`, `ny=100*y/height`; bottom이면 ny를 100-ny로 변환한다. 원래 공격 방향이 right→left일 때 양축을 `(100-nx,100-ny)`로 180도 회전한다.
- StatsBomb 후보 설정은 width=120,height=80,left_to_right,top이다. 원래 공격 방향 정규화 여부는 provider 문서 확인 후 적용한다. 전후반이라고 자동 flip하지 않는다. 이벤트 주체가 수비팀일 때 방향 규약도 검증해야 한다.
- 좌표 하나만 없거나 범위 밖·NaN·Inf이면 오류. 좌표 쌍이 모두 null이면 유지. clamp/추측하지 않는다. source 좌표 4개를 유지하고 transform ID를 저장한다.
- lane y 경계: left wing [0,20), left half-space [20,40), centre [40,60), right half-space [60,80), right wing [80,100].
- longitudinal x 경계: defensive [0,100/3), middle [100/3,200/3), final [200/3,100]. 경계점은 오른쪽 구간으로 들어간다.
- penalty area는 독립 bool overlay: x≥85, 22.5≤y≤77.5. StatsBomb 120×80의 x≥102,18≤y≤62 비례 규약을 버전 이름에 명시한다. 105×68 미터 pitch의 실제 박스 비율과 무조건 같다고 가정하지 않는다. 다른 소스는 box equivalence를 확인하거나 별도 정책이 필요하다.
- 따라서 5×3개의 배타 구역 + box flag이며, 박스를 네 번째 배타 third로 세지 않는다. 360은 frame subset이므로 연속 이동이나 보이지 않는 선수의 위치를 만들지 않는다.

## 정규화·availability 정책

`metric_p90 = metric_raw * 90 / minutes_played`. 값이나 minutes가 null 또는 minutes=0이면 per90은 null이다. 저장된 p90은 raw/minutes와 일치하는지 검증한다. share, 평균 좌표, completion, context에 per90을 만들지 않는다. source 제공 p90만 있고 raw가 없으면 이번 계약의 p90 컬럼은 unavailable이다.

Possession-adjustment는 **미구현**이다. StatsBomb possession_id는 유효한 팀 possession 분모와 동일하다고 단정할 수 없다. 향후 분모 계약은 `team_possessions_while_on_pitch`(선수 출전 구간의 완전하고 소유 팀이 식별된 possession 수), `possession_denominator_definition_id`, `possession_denominator_coverage`다. 이것과 동일 구간 numerator를 검증한 경우에만 별도 schema version에서 per_100_team_possessions 컬럼을 추가한다. 현재 임의 점유율 보정이나 숫자 컬럼은 생성하지 않는다.

null은 0이 아니다. 명확히 관측했으나 이벤트가 0회일 때만 0을 기록한다. missing reason 허용값은 not_collected / source_not_provided / definition_unverified / definition_incompatible / outside_visible_area / insufficient_minutes / access_failed / not_applicable다. 공급자 단위로 없는 공간값은 median 대체 대상이 아니다. coarse_proxy는 실제로 제공된 third/box 비중 등에만 사용하며 half-space·평균 위치로 승격할 수 없다.

## Role feature vector mapping

아래는 컬럼 선택 후보이며 score나 가중치가 아니다. 아직 관측되지 않은 항목은 자동으로 입력되지 않는다. key_passes/shot_assists처럼 중복되는 정의를 동시에 넣지 않도록 후속 feature selection에서 감사한다.

| role dimension | canonical inputs |
|---|---|
| progression_score_inputs | progressive_passes_p90, progressive_carries_p90, passes_into_final_third_p90 |
| creation_score_inputs | key_passes_p90, through_balls_p90, xA_p90, shot_creating_actions_p90 |
| carrying_score_inputs | carries_p90, carry_distance_p90, take_ons_completed_p90 |
| halfspace_usage_inputs | left_halfspace_touch_share, right_halfspace_touch_share |
| box_threat_inputs | non_penalty_xG_p90, shots_p90, penalty_area_receptions_p90, box_touch_share |
| combination_play_inputs | receptions_p90, passes_completed_p90, pass_completion |
| defensive_activity_inputs | pressures_p90, tackles_p90, interceptions_p90, recoveries_p90 |

## Numeric matrix와 누수 방지

`numeric_matrix(rows, columns, min_minutes=...)`는 명시적으로 선택한 공통 컬럼의 float list-of-lists를 반환한다. sklearn/numpy 변환 가능한 2차원 숫자 구조이며 torch는 후속 단계에서 tensor로 변환한다. 모델 객체·scaler·imputer는 없다. source/player/manager/결측 flag는 입력에 섞이지 않는다. 관측된 컬럼의 definition_id가 서로 다르면 오류로 종료한다. 이 문자열 일치만으로 실질적 정의 동등성이 증명되는 것은 아니며 ingestion에서 승인된 정의 registry를 배정해야 한다.

기본 모드는 결측 하나라도 있으면 실패한다. `allow_missing=True`는 inspection 전용 NaN matrix다. 이 결과를 PCA/autoencoder에 바로 넣을 수 있다고 주장하지 않는다. 실제 모델 입력은 공통 완전 컬럼을 선택하거나 이후 train-only preprocessing으로 유한값을 보장한 후 사용한다. 자동 imputation/normalization은 이번 범위 밖이다.

그룹 키: match_id, player_id, player_season_id, team_season_id. 같은 player-match 중복은 공급자가 달라도 거절한다. 경기 일반화 평가는 match_id 단위, 미관측 선수 일반화는 player_id 단위를 분리하고 두 제약이 동시에 필요하면 연결 성분 또는 purge 기준을 설계한다. grouping key 존재만으로 train/test 누수가 자동 방지되는 것은 아니다. 같은 경기 양 팀, 반복 선수, rolling window의 공유 경기, prototype 자기 포함까지 후속 split audit이 필요하다.

## 감독 필터 및 집계 관계

Wirtz는 canonical player_id + Leverkusen team_id + 검증된 Alonso manager_id/manager_period로 필터링한다. Palmer도 Chelsea team_id + season + 검증된 manager_period를 사용한다. name은 표시용이다. stint registry의 날짜 범위는 [valid_from, valid_to)이며 실제 경기 감독 정보가 우선한다. 이 registry의 데이터 수집·구현은 Phase 3 이후 범위다. manager 정보가 없으면 null이고 날짜만 보고 임의 이름을 채우지 않는다.

## 검증과 종료 판정

프로젝트 루트에서 `python3 -m unittest discover -s tests -v`로 실행한다. synthetic fixture는 테스트 안에만 존재하며 실제 경기 수치처럼 외부 파일로 저장하지 않았다.

| 종료 조건 | 검증 범위 |
|---|---|
| Wirtz 한 경기 표현 | event/spatial flags가 있는 synthetic PlayerMatch validation |
| Palmer 한 경기 표현 | event 없는 synthetic match aggregate; 실제 match data 확보 주장은 아님 |
| 같은 feature 형태 | 전체 registry 키/순서 동일, 선택한 완전 컬럼 2×1 numeric matrix |
| aggregated fallback | match aggregate 허용, season aggregate 분리 및 match matrix 거절 |
| 모델 입력 숫자 행렬 | complete inputs float 변환, missing 기본 거절, inspect NaN 별도 |
| 좌표 일관성 | scale, 원점, 방향 회전, null, 범위 오류, lane/third/box 경계 |
| 명시적 missing | 값/상태/사유/정의 버전 일관성, unavailable 공간 입력 차단 |
| 공급자 격리 | raw payload 보존, canonical allowlist, definition 충돌 차단 |

추가 검증: 중복 player-match, 음수/비정수 count, 분모 0, 20분 필터, per90 정합성, score-state 시간 합, 원본/표준 좌표 쌍, period 잘못된 feature. 이 검증은 스키마 계약의 검증이며 실제 데이터 ingestion 성공이나 통계적 타당성 검증이 아니다.

## Phase 3 입력과 blocker

확정 출처 후보는 StatsBomb Open Data의 레버쿠젠 2023/24 경기·라인업과 해당 경기 event/360이다. 이미 확보한 메타데이터부터 연결하되 event/360는 우선 소량 표본의 필드·UUID·출전시간 정의를 확인해야 한다. 상세 LICENSE 검토와 출처 표시 조건 확정이 필요하다.

Palmer 및 공통 비교군은 현재 **선정 완료된 합법적 집계 파일이 없다**. FBref advanced 현행 컬럼·시즌·이용 조건 검증 및 허용된 export 확보가 blocker다. 시즌 합계만 확보되면 player-match autoencoder는 실행할 수 없다. 최소 수십 명의 같은 제공자·정의·grain 데이터 확보도 남아 있다.

지금 unavailable: 공급자와 같은 정의의 touches/box touches, xA, SCA/GCA, turnovers, successful pressures; 신뢰할 수 있는 possession denominator; Palmer half-space/reception coordinates/시퀀스; 양 선수 연속 off-ball 이동·turn 동작. progression threshold, touch-derived 공간값, match tempo도 정의와 원필드 검증 전 채우지 않는다. StatsBomb event에서 산출 가능성이 있는 나머지 항목 역시 이번 Phase에서는 관측값을 생성하지 않았다.


## PHASE 2 REVIEW — 2026-09-16

새 데이터 다운로드·모델·Phase 3 adapter 구현 없이 현재 여섯 파일을 검토했다. 수정 후 테스트는 30 passed / 0 failed다.

| 순서 | 검토 항목 | 판정 및 근거 |
|---|---|---|
| 1 | 기본 분석 단위 | PASS: player_id + match_id 고유성; period aggregate 별도 |
| 2 | 계층 흐름 | PASS: payload → normalized event → PlayerMatch → 명시적 numeric columns; embedding 미구현 |
| 3 | 공급자 격리 | PASS: native ID와 payload는 보존하되 numeric 입력 allowlist에서 차단 |
| 4 | 실제 소스 변환 | 구조상 표현 가능; StatsBomb 메타데이터 외 실제 event·FBref 입력 검증은 미완료 |
| 5 | 동일 벡터 형태 | PASS: 서로 다른 synthetic 출처의 Wirtz/Palmer가 같은 91개 feature 키 보유; 값·가용성 동등성은 별개 |
| 6 | raw/per90 | PASS: 원수치 보존 및 분모 정합성; share/context에는 p90 미생성 |
| 7 | possession 보정 | PASS: 검증된 분모가 없어 컬럼·보정 계산 미생성 |
| 8 | 좌표 방향 | PASS: 지원된 입력 방향에서 0–100, 반대 방향 양축 회전; source 방향 설정 검증은 adapter 책임 |
| 9 | 가로 zone 배타성 | PASS: 20/40/60/80 직전·정확한 경계·직후를 expected label로 검사 |
| 10 | penalty/final third | PASS: penalty는 final third 안의 별도 overlay; 합산할 배타 zone 아님 |
| 11 | 100 경계 | PASS: (100,100)은 right wing/final third, pitch 내 포함 |
| 12 | 결측 | PASS: 관측 xA=0은 0.0, 미관측 xA는 null 및 사유; inspection matrix에서는 NaN |
| 13 | 짧은 출전 | PASS: 양의 출전 분이면 per90 계산; min_minutes는 후속 입력 필터, zero minutes는 null |
| 14 | 감독 필터 | PASS: canonical player/team/manager/period 키로 구분 가능; 감독별 실제 기간 검증은 아직 필요 |
| 15 | 숫자 입력 목록 | PASS: ML_FEATURE_COLUMNS는 context 제외 83개 후보 tuple; ROLE_DIMENSIONS는 역할별 subset |
| 16 | 누수 | context의 역할 입력 혼입 차단; split grouping 존재. 실제 split·target 설계 전 누수 부재를 보장하지 않음 |
| 17 | expected output | PASS: 경계 label/회전 좌표/실제 matrix 값과 오류 발생을 assertion |
| 18 | 전체 테스트 | 30 passed / 0 failed; python3 -m unittest discover -s tests -v |
| 19 | 이름 있는 synthetic 예제 | PASS: tests/test_schema.py의 test_named_synthetic_players_and_manager_filters |
| 20 | 복잡도 | 의존성 추가 없음; player-match/period 교차 검증은 공통 내부 함수 하나로 공유 |

### 수정한 결함

- pass_completion이 raw count와 모순되어도 통과하던 문제, 패스 시도 0인데 완료율 0을 허용하던 문제를 차단했다. raw count가 없는 외부 제공 완료율은 observed 값으로 저장할 수 있지만 정의 검증이 필요하다.
- period 테이블에는 누락돼 있던 성공 횟수 ≤ 시도 횟수, score-state 시간 합과 개별 상한 검증을 player-match와 공유했다.
- normalized event가 source 좌표만 가진 채 통과하던 문제를 차단했다. 변환 불가능한 이벤트는 raw에 보존하고 표준화 완료 행으로 내보내지 않는다.
- context 수치는 FEATURES에 남기되 ML_FEATURE_COLUMNS 및 numeric_matrix에서는 제외했다. team_shots/team_pass_volume의 dtype을 count 의미에 맞게 int로 수정했다.

ML_FEATURE_COLUMNS 전체를 그대로 모델에 넣으라는 의미는 아니다. raw/p90 중복, 유사 지표 중복, 결측 범위에 맞춰 공통 subset을 선택해야 한다. score-state 등의 context는 같은 경기 역할 설명의 환경 변수이며 반드시 미래 정보 누수인 것은 아니지만 역할 embedding에서 혼동되지 않도록 분리했다. 미래 경기 예측으로 목적을 바꾸면 당일 경기 통계도 예측 시점 이후 정보이므로 다시 점검해야 한다.

좌표 함수의 기본값은 이미 0–100/top/left-to-right인 입력 계약이다. 자동 방향 추론을 하지 않으므로 공급자가 다른 경우 명시적으로 width/height/direction/y_origin을 전달해야 한다. transform 문자열 존재와 범위 검증만으로 실제 원본의 방향이 맞다는 사실까지 증명하지 않는다.

### Synthetic 호환성 증빙

두 예제의 ID와 통계, Palmer 감독 기간은 모두 테스트용이며 실제 경기 결과가 아니다. 표시 이름만 Florian Wirtz/Bayer Leverkusen, Cole Palmer/Chelsea를 사용한다. Wirtz event형 출처와 Palmer aggregate형 출처에서 동일한 synthetic 정의를 적용했다. 선택 컬럼 [shots_raw, shots_p90] 결과는 [[2.0,9.0],[3.0,3.0]]이고 각각 20분/90분을 사용했다. 이 값으로 유사도나 선수 평가를 계산하지 않았다.

### Phase 3 진입 판정

NO: 스키마 코드 검토는 PASS지만 실제 ingestion의 데이터·이용 조건 gate는 남아 있다. StatsBomb LICENSE 세부 검토, event/360 좌표·출전시간·UUID 표본 검증, Palmer와 비교군의 합법적 집계 소스 및 grain/컬럼 정의 확정이 필요하다. FBref가 확보 가능하거나 두 소스의 정의가 동일하다고 간주하지 않는다. 이 리뷰에서는 새 데이터 접근을 하지 않았으므로 기존 blocker를 해소했다고 보고하지 않는다.
