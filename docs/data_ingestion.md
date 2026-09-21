> Milestone 1 update: full Bundesliga 2023/24 ingestion and event-only report commands are in [README](../README.md). The two-match counts and Phase 4 readiness below are historical Phase 3 results. Schema, cache, attribution and validation remain in use. 360 invalid linkage is now recorded without blocking event ingestion.

# Phase 3 — Real Data Ingestion

2026-09-17. 범위: 실제 raw/canonical 데이터, 좌표 변환, 저장·재로드·검증. per90, 전진 기준, 터치 집계, 역할 점수, PCA/UMAP, 신경망 및 앱은 구현하지 않았다.

## 실제 결과

| 항목 | 결과 |
|---|---|
| Primary | StatsBomb Open Data |
| Fallback | 권한 확인된 로컬 경기 집계 CSV용 adapter; 실제 Palmer 파일은 미확보 |
| Competition / season | 1. Bundesliga / 2023/2024 |
| 경기 | 3895052: 2023-08-19 Leverkusen–RB Leipzig; 3895292: 2024-04-06 Union Berlin–Leverkusen |
| 고유 선수 / 선수-경기 행 | 66 / 80 (벤치 명단 포함; 66명 모두 출전했다는 뜻 아님) |
| Event rows | 7,582 |
| Provider aggregate-stat rows | 0 (event를 집계해서 만드는 작업은 Phase 4) |
| Wirtz event rows | 373 |
| Wirtz aggregate rows | 0 |
| Palmer event / aggregate rows | 0 / 0 |
| Duplicate events | 0 |
| 360 | 3895052의 3,181 frames, 해당 경기 events의 85.0762%와 UUID 연결 확인 |
| 3895292 360 | 반복된 연결 reset으로 미확보; offline manifest에는 not_cached, 파일 부재 확정이 아님 |
| 테스트 | 53 passed / 0 failed |

선택한 두 경기는 서로 떨어진 날짜의 기능 검증 표본이며 대표성 있는 분석 코호트가 아니다. Wirtz 신원은 Phase 1에서 실제 lineup으로 확인한 source player ID 40724를 사용한다. Palmer의 native ID를 임의로 만들거나 이름 문자열로 식별하지 않았다.

## 실행 순서와 범위 통제

1. Phase 1/2 문서·구현·테스트 확인, 기존 30개 테스트 실행.
2. 공식 competitions.json 현재 내용, 라이선스 PDF, 이벤트 명세 확인.
3. synthetic fixture 테스트 작성 후 StatsBomb 및 local aggregate adapter 구현.
4. canonical integrity / typed Parquet 저장·재로드 / 품질 report 검사.
5. 실제 두 경기 로드, 동일 slice 재실행, 전체 테스트 확인.

전체 리그 다운로드는 하지 않았다. Runtime dependency는 `pyarrow==25.0.1`만 추가했다. pypdf는 이번 공식 PDF 확인을 위해 작업 환경에만 설치했으며 ingestion 의존성이 아니다. 저장소에 이미 검증된 adapter 구현은 없었고, 이 좁은 JSON mapping에 필요하지 않은 pandas/statsbombpy 및 모델 패키지는 추가하지 않았다.

```bash
# Python 3.11+, tested 3.13.5
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v

# Online: re-fetch competitions.json, resolve season_id, then reuse cached match files.
.venv/bin/python -m src.data.ingestion --source statsbomb --competition 9 --season 2023/2024 --match-limit 2

# Exact current slice. --offline explicitly uses and re-parses the cached catalogue.
.venv/bin/python -m src.data.ingestion --offline --match-limit 2 --match-id 3895052 --match-id 3895292
```

처음 online 실행의 DNS/TLS 오류 때문에 일부 파일은 승인된 curl 접근으로 확보한 뒤 같은 raw cache에 import했다. receipt에 원본 URL·SHA-256·원래 다운로드 파일 mtime 기반 시간·import 시간·시간 근거를 남겼다. 기존 경기 목록 및 3895292 lineup은 Phase 1의 원본을 재사용했으며 새 다운로드인 것처럼 표시하지 않았다. `competitions.json`은 이번 실행에서 공식 source로부터 직접 받았다. Import 과정은 canonical 내용을 변경하지 않았다.

기본 team_id=904, manager_id=1000310은 Phase 1의 실제 경기 metadata에서 확인한 식별자다. CLI로 다른 source-native ID를 선택할 수 있다. season_id는 하드코딩하지 않으며 현행 조회 결과가 281이었다. snapshot은 전체 저장소 commit을 pin하지 않으므로 파일별 checksum·retrieved_at으로 재현성을 관리한다. 기존 raw 파일을 수동 변경하면 checksum 오류로 종료한다.

## 소스 판단 및 이용 조건

### StatsBomb

[Open Data](https://github.com/statsbomb/open-data), [공식 LICENSE](https://github.com/statsbomb/open-data/blob/master/LICENSE.pdf), [공식 명세 v1.1](https://github.com/statsbomb/open-data/blob/master/doc/StatsBomb%20Open%20Data%20Specification%20v1.1.pdf)를 사용한다. 로컬 기존 LICENSE.pdf에서 2023-09-08 버전의 본문을 판독했다. 연구·비상업 목적, 원자료 외부 제공 및 상업적 활용 제한, 분석 공개 시 브랜드 로고 표시 조건을 확인했다. README의 StatsBomb 출처 표시도 따른다. 약관은 resource centre에 사용자 등록을 요청하지만 이 작업에서 개인정보를 전송하지 않았다. 로컬 변환 결과는 연구용이며 원자료·processed 자료·실제 fixture를 외부에 배포하지 않는다. `.gitignore`는 legacy `data/availability/`까지 제외한다.

현재 catalogue의 Premier League 시즌은 2003/2004, 2015/2016이다. 따라서 'StatsBomb에는 PL가 전혀 없다'는 전제를 그대로 사용하지 않는다. **Palmer의 Chelsea 분석 시즌에 해당하는 PL event 데이터가 catalogue에 없다는 것**이 실제 제한이다. 대표팀 event를 Chelsea 역할의 대체 표본으로 합치지 않았다.

### FBref / 집계 fallback

[Sports Reference 공식 2026-01 공지](https://www.sports-reference.com/blog/category/advanced-stats/)는 공급자 계약 종료에 따른 advanced 데이터 삭제를 설명한다. [현행 data-use 안내](https://www.sports-reference.com/data_use.html)는 ML 관련 사용 제한도 명시한다. 따라서 Phase 1의 조건부 fallback이 자동으로 사용 가능해진 것이 아니다. 차단을 우회하거나 scraping하지 않았으며 과거 파일의 무단 mirror도 사용하지 않았다. Kaggle/GitHub/Understat 역시 Phase 1에서 이용 가능 범위가 확정된 Palmer 파일이 없었으므로 검증된 fallback인 것처럼 채택하지 않았다.

로컬 CSV adapter는 공급자 통계와 이용 권한이 확인된 파일을 가져오는 경로만 제공한다. metadata 파일에 문자열을 적는 것이 법적 권한을 새로 부여하지 않는다. 실제 입력 전 원출처와 허용 용도를 확인해야 한다.

## 구조와 기존 schema 연결

| 파일 | 역할 |
|---|---|
| sources/base.py | deterministic namespace, raw JSON cache, source receipt; 상속 hierarchy 없음 |
| sources/statsbomb.py | source discovery/load 및 match/player/event mapping, source lineup 시간 해석 |
| sources/aggregate_csv.py | 허용된 로컬 raw match-stat CSV mapping; event 합성·scraping 없음 |
| ingestion.py | CLI, 소량 조립, 명시적 Arrow schema, snapshot 저장·재로드 |
| validation.py | 기존 dataclass 검증, 관계/시각/좌표/중복 검사, 재사용 품질 보고서 |

기존 `schema.py`, `coordinate_normalization.py`, `pitch_zones.py`는 변경하지 않았다. event는 `NormalizedEvent`로 검증하고, 선수-경기 metadata는 `PlayerMatch`로 검증한다. 저장 테이블은 다음처럼 구성한다.

| Table | Grain / key | 내용 |
|---|---|---|
| raw JSON | 제공자 원본 파일 | 필드 손실 없는 source payload; file path + source_event_id/index로 추적 |
| matches.parquet | source match / match_id | source/canonical ID, 날짜·시즌·팀·득점·감독·초기 formation |
| players.parquet | player-match / match_id+player_id | PlayerMatch metadata; feature dict를 생성·저장하지 않음; shirt_number/starter/minutes_method 추가 |
| events.parquet | event / data_source+source_match_id+source_event_id | NormalizedEvent 필드 + nullable timestamp/event_subtype/related_player_id |
| player_match_aggregate_stats.parquet | player-match / source+match+player | player metadata + provider가 이미 보고한 raw statistics; 지금은 typed empty table |

명시적 Arrow schema가 빈 테이블이나 전체 null 컬럼에도 dtype을 유지한다. 데이터 타입 추론에 의존하지 않는다. Date는 기존 계약의 ISO string을 유지한다. timestamp는 period elapsed time이며 nominal minute와 교차검증한다. event_subtype은 선택적 표준화 label, related_player_id는 pass recipient나 substitution replacement처럼 의미가 명확한 경우에만 기록한다. provider의 임의 qualifier를 수십 개의 분석 컬럼으로 노출하지 않으며 원본에서 보존한다.

ID는 `statsbomb:match:3895052`, `statsbomb:player:40724`처럼 source namespace를 가진다. event key는 match까지 포함한다. 이벤트 ID가 없으면 source의 안정적인 index를 `index:<n>`으로 사용하고 중복 index도 거절한다. 서로 다른 공급자의 동일 실존 선수를 자동으로 합치지는 않는다; 향후 검증된 identity mapping이 필요하다.

### Aggregate-only 계약

Section 8-A의 별도 테이블은 기존 registry의 `*_raw` 명명 규칙을 재사용한다. 예: provider progressive_passes → progressive_passes_raw, xg → xG_raw, npxg → non_penalty_xG_raw, xa → xA_raw, touches_pen_area → box_touches_raw. attacking-third count는 새 분석 feature가 아니라 source raw 값 보존용 `touches_att_third_raw`로 보관한다. 매핑된 원컬럼명은 manifest의 column_map에 남는다. 해당 값이 없는 경우 null이며 p90 컬럼은 테이블에 존재하지 않는다.

집계 CSV의 최소 metadata header:

```
source_match_id,source_player_id,source_team_id,source_opponent_id,player_name,team_name,opponent_name,competition,season,match_date,home_away,minutes_played
```

통계 header는 제공자 원컬럼명을 유지하고 다음과 같은 별도 metadata JSON으로 mapping한다. 아래는 형식 설명용이며 실제 source나 권한을 주장하지 않는다.

```json
{
  "source_name": "approved_export",
  "source_version": "documented-export-version",
  "source_url": "https://example.invalid/source",
  "license_notice": "Record the actual applicable licence here before use",
  "permission_basis": "Record actual permission/licence evidence before use",
  "event_definition_notes": "Record provider definitions before use",
  "column_map": {"shots_raw": "Shots", "xA_raw": "xA"}
}
```

```bash
.venv/bin/python -m src.data.ingestion --source approved-csv --aggregate-file /path/to/approved.csv --aggregate-metadata /path/to/provenance.json --match-limit 2 --output-dir data/processed/approved-export
```

빈 문자열은 null, 명시적 `0`은 0으로 읽는다. NaN/Inf/음수/소수 count는 거절한다. 날짜와 경기 ID가 없는 season aggregate를 경기 행으로 변환하지 않는다. registry 밖 또는 p90 column_map을 거절한다. 입력 CSV와 metadata는 해시 이름으로 raw cache에 보존한다. 실제 source retrieved_at을 모르면 null이고 local loaded_at을 따로 기록한다. `target_player_ids`를 제공할 때도 검증된 source ID만 사용한다.

## 좌표·taxonomy·결측

공식 명세 Appendix 2의 120×80/top-origin 좌표 도표와 pass angle 정의(0 방향은 해당 팀 공격 골대)를 확인했다. adapter는 **event-team 기준으로 이미 오른쪽을 향하는 source 규약**을 적용한다. possession_team이나 home/away, 전후반만 보고 재반전하지 않는다. 수비 이벤트에도 같은 event-team convention을 적용하는 assumption을 manifest와 코드에 명시했다. 이 convention의 실제 의미와 경기 영상 정합성을 전수 검증한 것은 아니다.

기존 함수로 source x/120×100, y/80×100을 계산하고 네 source coordinate를 모두 보존한다. 시작/end 위치가 제공되지 않는 이벤트는 null이다. 범위 밖 좌표를 clamp하지 않는다. shot z는 raw에 보존하고 canonical 2D에는 앞 두 축만 저장한다.

PASS/CARRY/SHOT/DRIBBLE/RECEIPT/PRESSURE/TACKLE/INTERCEPTION/RECOVERY/FOUL/OTHER taxonomy를 사용한다. Duel 중 source subtype=Tackle만 TACKLE로 map하고, 신규·비대상 type은 OTHER로 보존한다. pass/receipt의 outcome 생략은 명세에 따라 COMPLETE로 map한다. under_pressure의 생략은 확실한 false라고 가정하지 않고 null을 보존한다. unknown player를 만들어내지 않는다; OTHER의 팀 단위 관리 이벤트에는 player_id null을 허용하고, player action에서는 선수 ID와 lineup 관계를 요구한다.

## 출전시간·감독

공식 lineup의 position intervals를 사용하고 event Half End timestamp로 각 period 실제 길이를 보완한다. source nominal 45/90/105분 기준 clock을 period elapsed로 변환한 뒤 겹치는 role interval을 합친다. 전후반 휴식은 제외하고 stoppage/extra time은 포함한다. provider가 일반적으로 표시하는 반올림 90분과 달라질 수 있다. 예를 들어 이 slice에서 Wirtz Union전은 104.9023분이다. 단순히 90분으로 잘라내지 않았다.

position interval·period 종료가 없거나 clock이 모순되면 null이다. Player Off/On의 임시 이탈은 정확한 interval coverage가 불명확하여 null과 사유를 기록한다. unused lineup member를 출전 선수로 가정하지 않는다. 현재 80개 player-match metadata 중 22개는 minutes unknown이며 분석 sample 필터가 후속 단계에서 필요하다.

manager는 match의 실제 managers 객체에서만 가져온다. manager_period는 연속 재임 구간의 별도 근거가 없으므로 null이다. Wirtz+Leverkusen+Alonso manager ID+season/date 필터는 가능하지만 독립적인 재임기간 테이블을 완료한 것으로 주장하지 않는다. 초기 formation만 보존하고 경기 중 역할 변화를 요약하지 않았다.

## 360 및 품질 보고

360은 event UUID 연결·중복 여부를 검증하고 **raw 상태로 보관**했다. 프레임 좌표를 canonical spatial table로 확장하거나 오프더볼 경로/하프스페이스 feature를 계산하지 않았다. 좌표가 있는 이벤트의 주변 선수 맥락을 추가하므로 후속 Level 2 분석을 더 풍부하게 만들 수 있지만, 연속 tracking이나 모든 이벤트에 대한 위치 정보를 제공하지 않는다. 현재 360의 좌표/visible-area 자체 전수 품질 검사는 범위 밖이다.

`quality_report.json`은 경기/고유 선수/player-match/event/aggregate 수, taxonomy counts, ID·시작/end 좌표 null 비율, 중복, 좌표 min/max, 대회·시즌, 검증된 target ID별 event/aggregate 행 수, 출전시간 미상 행 수를 기록한다. 실제 좌표 min/max는 모두 0–100 안이다. end coordinate 결측률은 end location이 정의되지 않는 이벤트를 포함한 전체 분모이므로 오류율과 동일하지 않다.

`manifest.json`은 source snapshot version, retrieved_at 및 파일별 receipt, competitions/seasons, schema_version=2.0.1, ingestion_version=3.0, typed output 해시, 라이선스 notice, 360 접근 상태와 coverage를 기록한다. missing source 파일을 not_found로 단정하지 않는다.

## 재실행·저장 안전성·검증

같은 slice는 append하지 않고 네 테이블 전체 snapshot을 교체한다. 저장 전 validation, 임시 파일의 typed Parquet 재로드 및 값 동일성 검증을 수행한다. manifest를 마지막에 교체하고 파일 checksum으로 불완전 snapshot을 감지한다. 여러 프로세스의 동시 쓰기나 다중 파일 filesystem transaction을 지원하는 DB는 아니다. 서로 다른 source slice는 별도 output-dir를 사용한다.

테스트는 synthetic fixture와 mocked I/O만 사용하며 인터넷에 의존하지 않는다. 기존 Phase 2 30개를 포함한 총 53개가 통과했다. source mapping, ID 보존, unknown OTHER, missing player/coordinate, half-time double flip, corner coordinates, 중복 및 잘못된 event 순서/팀 관계/시각, 추가시간·연장전·교체 선수, aggregate-only CSV 및 0/null, raw checksum/cache refresh/offline, 360 UUID, Parquet dtype/value 재로드와 repeated writes를 검증한다.

## Phase 4 readiness

**전체 Wirtz–Palmer 비교: NO.** Wirtz event ingestion의 실제 end-to-end 검증은 완료했다. 그러나 Palmer의 허용된 실제 match aggregate, 공통 정의, 최소 수십 명 비교군이 없다. aggregate adapter는 synthetic compatibility 테스트만 완료했고 실제 Palmer 통계를 확보한 것으로 표시하지 않는다. Wirtz와 Palmer의 같은-source 비교도 현재 불가능하다.

후속 입력 후보는 현재 `matches.parquet`, `players.parquet`, `events.parquet`와 UUID 검증된 raw 360이다. `player_match_aggregate_stats.parquet`는 schema가 있는 빈 테이블이다. Wirtz 단독 feature engineering을 위한 입력은 준비됐지만 이번 작업에서는 Phase 4를 시작하지 않았다. xA/xG와 progressive action 등 서로 다른 공급자 정의를 동일시하지 않으며, 데이터·이용 권한을 확인하기 전 공통 feature가 존재한다고 간주하지 않는다.
