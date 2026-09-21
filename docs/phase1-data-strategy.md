# Phase 1 — 데이터 가용성 조사 및 권고

조사일: 2026-09-14. 상태: **StatsBomb 시즌 메타데이터 검증 완료 / 전체 소스 조사는 미완료**.

## 1. 실제 확인한 것과 미확인 항목

현재 작업 디렉터리에 기존 프로젝트 파일은 없었다. `.agents`, `.git`에서 읽을 수 있는 작업 지침 파일도 발견되지 않았다. git 실행 파일은 없으므로 Git 저장소 상태 자체는 검사하지 못했다. 이번 변경은 조사 문서와 출처 증빙에 한정한다.

공식 [StatsBomb 경기 목록](https://raw.githubusercontent.com/statsbomb/open-data/master/data/matches/9/281.json)을 내려받아 JSON 파싱으로 확인했다.

| 검증 항목 | 실제 결과 |
|---|---|
| competition / season ID | 9 / 281 |
| 경기 수 | 34 |
| 레버쿠젠 포함 여부 | 34경기 모두 team_id 904 포함 |
| 날짜 범위 | 2023-08-19 ~ 2024-05-18 |
| 360 공개 상태 | 34경기 모두 `match_status_360=available` |
| 감독 | 레버쿠젠 측 모두 `Xabier Alonso Olano` |
| 포함 팀 | 레버쿠젠 + 분데스리가 나머지 17팀 |

이는 **레버쿠젠의 리그 전체 시즌**이지 분데스리가 전체 306경기가 아니다. Wirtz가 34경기에 모두 출전했다는 의미도 아니다. 개별 event 및 three-sixty 파일의 존재·파싱·event UUID 결합률·visible area·선수별 출전시간 검증은 남아 있다.

[표본 라인업](https://raw.githubusercontent.com/statsbomb/open-data/master/data/lineups/3895292.json)에서 Wirtz(40724), Hofmann(8804), Adli(33401), Grimaldo(10336)를 확인했다. 라인업 등재 자체가 해당 경기 출전이나 동일 역할 수행의 증거는 아니다.

공식 [README](https://github.com/statsbomb/open-data/blob/master/README.md)는 event/lineup 및 일부 경기의 360 JSON 구조, 연구 결과 공개 시 출처·로고 표시 요구를 설명한다. 로컬에 원문을 저장했다. [LICENSE.pdf](https://github.com/statsbomb/open-data/blob/master/LICENSE.pdf)도 내려받았으나 PDF 텍스트 판독 도구가 없어 세부 조항을 검토하지 못했다.

외부 검증 장애: web 도구 연결 실패, FBref/Sports Reference DNS 실패, 전체 competitions.json 전송 timeout/reset. 최초 부분 응답에는 Bundesliga 2023/24와 360 제공 메타데이터가 있었으나 전체 JSON은 확보하지 못했다. 실패를 자료 부재로 해석하지 않는다.

## 2. 선수·시즌별 가용성

| 선수 / 시즌 | Event·360 | 집계 데이터 | 판정 |
|---|---|---|---|
| Wirtz 레버쿠젠 2022/23 | 해당 시즌 공개 목록 미확인 | FBref 현행 제공 미확인 | 후보; 감독별 경기 구분 필수 |
| Wirtz 레버쿠젠 2023/24 | 팀 34경기 available 메타데이터 확인 | event에서 자체 산출 가능; FBref 미확인 | 우선 분석 시즌 |
| Wirtz 레버쿠젠 2024/25 | 해당 시즌 공개 목록 미확인 | FBref 현행 제공 미확인 | 확장 후보 |
| Palmer 첼시 2023/24 | 첼시 리그 event 부재라는 사용자 전제; 전체 목록 독립 검증 미완료 | advanced 항목 및 사용 조건 미확인 | 공통 비교 우선 후보 |
| Palmer 첼시 2024/25 | 동일 | 동일 | 별도 season-manager 후보 |
| Palmer 2025/26 및 이후 | 실제 구단·감독·공개 범위 미검증 | 미검증 | 현재 시즌까지 확보됐다고 주장하지 않음 |

2023/24가 Alonso–Wirtz의 **마지막 풀시즌**이라는 설명은 채택하지 않는다. 요청 자체에서 2024/25도 Alonso 분석 범위로 지정했으므로 2023/24는 여기서 '공개 데이터 우선 시즌'으로 부른다. 감독 부임일은 2022-10-05를 확인 후보로 두고 공식 구단 발표 및 match manager와 교차검증 후 확정한다. 2022/23 시즌 합계만 있으면 Alonso 이전 구간을 날짜로 분리할 수 없으므로 Alonso 전용 분석에서 제외한다.

대표팀 대회에서 Palmer/Wirtz event가 발견되더라도 첼시/Alonso 역할의 대체 데이터로 합치지 않는다. 별도의 일반화 실험만 가능하다.

## 3. 무료 소스 후보 비교

아래 링크 중 StatsBomb의 명시한 파일 외에는 이번 환경에서 본문을 검증하지 못했다. 표의 미확인은 '사용 가능' 판정이 아니다.

| 소스 | 해상도·장점 | 단점·시즌 범위 | 라이선스·재배포·접근 | 갱신 |
|---|---|---|---|---|
| [StatsBomb Open Data](https://github.com/statsbomb/open-data) | event/lineup/선택적 360; 레버쿠젠 23/24 팀 전체 리그 목록 확인 | 표적 팀 중심 표본; 모든 시즌/리그 아님; 360은 tracking 아님 | README 출처·로고 요구 확인; LICENSE 상세 미검토, 원자료 재배포 미승인; 캐시 사용, GitHub 현행 한도 별도 확인 | 저장소 변경 기반, 정기 갱신 보장 미확인 |
| [FBref](https://fbref.com/) | 다리그 선수 집계 공통 표본 후보 | 현재 advanced 제공 여부·과거 시즌 유지 여부 모두 재검증 필요 | [데이터 이용 안내](https://www.sports-reference.com/data_use.html) 확인 실패; 자동 수집·우회 금지, 허용된 수동 export/승인 경로만 후보; 재배포 미확인 | 현행 주기 미확인 |
| [Kaggle](https://www.kaggle.com/datasets) | 공개 집계/event 파일 후보 | 정확한 dataset·버전·원출처 미선정; 최신 선수 포함 보장 없음 | 게시자 라이선스뿐 아니라 원제공자 권리 확인 필요; 무료 다운로드≠재배포 허용 | 게시자별 |
| [Wyscout 공개 연구 저장소](https://github.com/koenvo/wyscout-soccer-match-event-dataset) 및 [원 논문](https://www.nature.com/articles/s41597-019-0247-7) | 역사적 다리그 event 비교군 후보 | 본문·라이선스·시즌 미검증; 목표 선수 시즌 직접 비교로 채택 불가 | 코드 라이선스와 데이터 라이선스 별도 검토 | 연구용 정적 배포 후보 |
| [기타 GitHub](https://github.com/) | 이미 정리된 공개 데이터 탐색 가능 | 원제공자 데이터 무단 복제·정의 불명 가능; 현재 채택 자료 없음 | 원출처·버전·권한 추적 필수 | 저장소별 |
| [Understat](https://understat.com/) | 슈팅/xG 중심 보조 데이터 후보 | 패스·수신·캐리 네트워크의 대체재 아님; 선수별 실제 시즌 미확인 | 약관·자동접근·재배포 미확인; 아직 수집하지 않음 | 현행 주기 미확인 |

현재 **확정 소스는 StatsBomb의 확인된 메타데이터뿐**이다. FBref advanced가 과거에 존재했다는 사실만으로 지금 확보 가능하다고 전제하지 않는다. 대체 소스를 아직 검증하지 못했으므로 무료 데이터만으로 전체 목표가 가능하다는 결론도 유보한다.

## 4. 비교군 전략

주 비교군: 같은 제공자에서 같은 시즌의 유럽 주요 리그 AM/윙/공격형 8번/세컨드 스트라이커를 최소 수십 명 확보한다. 잠정 900분 이상을 기준으로 하고 600/1200분 민감도 분석을 계획한다. 명단은 포지션·출전시간·구단·감독을 확인한 후 확정한다. 선수-시즌 행 수와 고유 선수 수를 구분한다.

예비 검색 대상은 Wirtz, Palmer, Ødegaard, Musiala, Xavi Simons, Brandt, Foden, Maddison, Eze, Bruno Fernandes, Olmo, Griezmann, Dybala 등이다. 실제 데이터 확보 명단이나 현재 소속을 뜻하지 않는다. 선수별 동일 스키마 availability 행을 작성해야 한다.

event 비교군은 레버쿠젠 선수 및 상대팀의 출전 선수에서 구성할 수 있다. 다만 상대 선수는 레버쿠젠을 만난 1~2경기 표본에 가깝고 Wirtz의 시즌 표본과 불균형하다. 이를 유럽 AM 전체 공간이나 공정한 시즌 순위라고 표현하지 않는다. 다른 공개 대회는 별도 cohort로 관리한다.

Alonso prototype 후보는 라인업에서 확인한 Wirtz/Adli/Hofmann이다. Grimaldo는 역할과 윙백 성격을 검증하기 전 핵심 AM centroid에 넣지 않고 확장 prototype 후보로 둔다. 위치·출전시간·역할 구간 기준 확정이 선행돼야 한다.

## 5. Feature 가용성 초안

여기서 '산출 후보'는 필드·정의 검증 전 상태이며 실제 측정 완료가 아니다.

| Level | Feature | Wirtz event에서 산출 후보 | Palmer 집계 fallback |
|---|---|---|---|
| 1 | 패스 시도/성공, 슛, 태클, 가로채기, carry, dispossession | 이벤트 정의에 따라 count/per90 | 동일 정의의 제공 항목에 한함 |
| 1 | progressive pass/carry, final-third·box 진입 | 좌표·명시적 자체 정의 필요 | 공급자 정의와 일치하지 않으면 주 비교에서 제외 |
| 1 | xG/npxG | shot xG와 penalty 구분 | 다른 xG 모델과 직접 혼합 금지 |
| 1 | xA/key pass/through ball | shot assist 연결/qualifier 확인; xA와 xG assisted 구분 | 동일 제공자 항목만 |
| 1 | touches, zone touches, turnovers, SCA/GCA | 이벤트 단순 합은 touches가 아님; 공식 집계와 같다고 가정 금지 | 현재 컬럼 존재 여부 확인 필수 |
| 1 | pressures | 해당 이벤트 필드 검증 필요 | 공개 집계에 없으면 unavailable |
| 2 | 평균 event touch/reception 위치, pass origin/destination, carry start/end, shot 위치 | 필드가 있는 이벤트 기반으로 가능 | 슈팅 좌표가 별도 확보되더라도 touch 좌표로 대체 불가 |
| 2 | 5개 가로 lane × 세로 thirds 점유율 | 좌표에서 계산; 수신 이벤트 coverage 표시 | third·box 집계만 조건부 사용; half-space 복원 불가 |
| 2 | 압박 이벤트 위치·주변 선수 분포 | pressure 좌표/360 visible area 범위 내 | 불가 |
| 3 | reception 이후 pass/carry/dribble/shot 순서 | player/possession/시간/related event 연결 검증 후 가능 | 불가; season aggregate로 시퀀스 합성 금지 |
| 3 | turn, layoff 이후 box movement, off-ball transition run | 이벤트만으로 직접 관측 불가; tracking/영상 필요 | 불가 |

per90은 count × 90 / 실제 출전 분으로 산출한다. 비율·평균 좌표·완료율을 다시 per90 변환하지 않는다. possession adjustment는 분모가 확보된 지표만 정의를 기록해 산출한다. team possession 추정치와 공식 possession을 구분한다.

zone 설계: thirds와 penalty area는 겹치므로 5×4개의 독립 구획으로 그대로 세면 이중 집계된다. lane×third의 15개 배타 구역과 `inside_penalty_area` 별도 플래그를 권고한다. 20개 구획이 꼭 필요하면 box 우선 할당 및 final-third-excluding-box를 명시해야 한다. 하프스페이스 경계는 측정 규약이지 유일한 전술적 정답이 아니다.

평균 이벤트 위치는 선수의 경기 전체 평균 위치가 아니다. 360의 관측되지 않은 선수를 빈 공간으로 해석하지 않는다. '수비 블록 높이'는 관측 범위 내 이벤트 순간 proxy임을 표시하며 연속 tracking 변수로 취급하지 않는다.

## 6. 가장 현실적인 전략

**권고: 공통 집계 비교 + Wirtz 전용 공간 분석의 두 경로.**

1. 2023/24부터 같은 집계 제공자로 Wirtz·Palmer·최소 수십 명의 비교군을 확보한다. 실제 확보/합법적 접근이 확인되기 전에는 학습을 시작하지 않는다.
2. 제공자·metric definition·season-manager·집계 grain이 같은 공통 feature로 cosine/PCA를 만든다. UMAP은 탐색 시각화이며 원공간 순위의 근거로 사용하지 않는다.
3. StatsBomb Wirtz event/360으로 수신·패스·캐리·압박 공간 프로필을 별도로 만든다. FBref third 비중은 coarse aggregate로 표시한다. 이것으로 Palmer half-space 점수를 만들지 않는다.
4. 공통 advanced 데이터가 확보되지 않으면 검증된 기본 통계만으로 연구 질문을 축소하거나 데이터 확보 대기 상태로 둔다. 슈팅 전용 데이터로 전체 역할 적합성을 주장하지 않는다.

대안 A: event-only. Wirtz 연구는 가능하지만 첼시 Palmer 비교를 충족하지 못한다. 대안 B: 제공자·해상도를 혼합해 결측을 채운 단일 embedding. 선수 역할 대신 데이터 출처를 학습할 위험이 커 권고하지 않는다.

결측 정책 초안: 구조적 미관측은 imputable missing과 분리한다. Palmer 전체에 없는 half-space·시퀀스는 전체 비교 feature에서 제외한다. 공통 feature의 일반 결측률이 학습 표본에서 30%를 넘으면 제외; 그 이하는 학습 데이터에서만 계산한 median 대체를 후보로 둔다. 작은 position 그룹의 median은 불안정하므로 그룹 크기 기준을 후속 설계에서 확정한다. 결측률·대체 여부·제외 이유를 보고한다.

스코어 후보: 학습 cohort에서 표준화한 공통 벡터 z에 대해 `100×(1+cos(zA,zB))/2`. 음수 cosine도 포함하는 선형 변환이며 적응 성공 확률이 아니다. 카테고리는 양쪽 관측 가능 feature가 충분할 때만 계산하고 0-norm·한쪽 전체 결측은 N/A. 전체 점수의 포함 범위와 coverage를 함께 표시한다. 현재 실제 점수와 nearest-neighbour 순위는 계산하지 않았다.

Alonso fit은 같은 공통 집계 공간에서 동역할 선수별 centroid를 만든 뒤 선수 균등 가중 평균을 기본 후보로 한다. Wirtz 자기 포함 편향을 피하려면 Wirtz 제외 prototype에서 Wirtz와 Palmer를 동일하게 평가한다. 후보 부족·역할 검증 실패 시 fit score를 내지 않는다. Grimaldo 포함 여부와 분 가중치 변경은 민감도 분석 대상이다.

Autoencoder는 계절 집계만 확보되면 player-match 입력 조건을 충족하지 않으므로 보류한다. 경기 데이터가 생겨도 고유 선수 수·독립 경기 수·baseline 대비 검증이 먼저다. season 데이터를 복제해 match 표본을 만들지 않는다. 같은 경기의 양 팀과 같은 선수의 시즌을 임의 분할하면 누수가 생기므로 평가 목적에 따라 match group과 player group을 모두 감사한다. 모든 전처리는 train에만 fit한다.

## 7. Context와 해석 한계

event 경로는 경기 시간·득점 상태·홈/원정·라인업·포메이션 변경·팀 패스량 등을 검증 후 만들 수 있다. possession %, 상대 블록 높이, nominal position은 정의와 관측 범위를 구분한다. 집계 경로는 팀/리그/시즌·팀 점유율 등의 실제 확보 변수만 통제할 수 있다. 경기별 감독 정보가 없으면 season-manager 분할을 발명하지 않는다.

context residualization이나 팀 단위 표준화는 관측 환경과의 상관을 조정할 뿐 개인 능력의 인과적 분리가 아니다. 현재 데이터로 Palmer의 Alonso 적응 성공, 비관측 오프더볼 경로, half-space 수신 빈도, 팀 전술과 개인 특성의 완전 분리를 확실히 말할 수 없다. 기존 여섯 연구 질문의 실증 답변은 후속 분석 전까지 유보한다.

## 8. Phase 1 통과 조건과 현재 결론

- 완료: 기존 파일 탐색, 공식 34경기 JSON 파싱, 팀/감독/날짜/360 status 확인, 표본 라인업 식별, 공식 README 확보, 데이터 전략 및 스키마 초안.
- 미완료: 전체 competitions.json으로 Chelsea 및 다른 시즌 부재/존재 검증, event/360 표본 필드 검증, FBref 현행 advanced·약관 확인, 대체 소스 실제 dataset 선정, 최소 수십 명 공통 집계 coverage 확인, 상세 라이선스 검토.
- 다음 단계에 필요한 데이터: 합법적 경로로 확보한 공통 제공자의 player-season 또는 player-match 파일, 정의 문서, 출전시간·감독 구간; StatsBomb 표본 event/360 및 UUID coverage.
- 현재 판정: **Wirtz 2023/24 공간 연구의 공개 메타데이터 근거는 확보. Palmer를 포함한 공통 역할 비교의 실현 가능성은 조건부. Phase 2로 진행하지 않음.**
