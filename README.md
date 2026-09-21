# Football Player Role Analysis

## Milestone 3 — Alonso Tactical Role Encoder v1

기존 M2의 적격 player-match 376행과 15개 전술 피처를 사용하는 CPU 오토인코더
기준선이다. 경기 단위 분할에서 학습 전용 StandardScaler/PCA와 비교하며,
시드 42~51의 10회 평가 및 시드 42 모델을 저장한다.

```bash
.venv/bin/python -m src.models.train_tactical_encoder
.venv/bin/python -m pytest -q
```

동일 학습 명령을 두 번 실행하면 기존 metrics.json과 시드 42 test MSE를 비교해
차이 1e-5 이내인지 검증한다. pytest가 없다면 테스트 실행 도구로
`.venv/bin/python -m pip install pytest`를 사용한다. 추가 직접 런타임 의존성은
공식 CPU wheel로 고정한 PyTorch뿐이다.

- [M3 모델 보고서](outputs/alonso_tactical_encoder_v1/model_report.md)
- [M3 평가 수치](outputs/alonso_tactical_encoder_v1/metrics.json)
- 모델: `models/alonso_tactical_encoder_v1/`
- 추론: `src.models.inference.encode_player_match(features)`,
  `encode_player_dataset(df)`, `compare_to_role_prototypes(embedding)`

추론에는 feature_order.json의 15개 원본 피처 값을 이름과 함께 전달한다.
결측·비수치·NaN/inf는 오류, 추가 열은 경고 후 무시한다. 반환값은 임베딩,
프로토타입 유사도 및 거리, 피처 가용성과 학습 범위 밖 여부이다.
프로토타입과 시즌 요약은 전체 관측의 기술적 요약이며 외부 선수 검증이 아니다.

---

아래는 Milestone 1까지의 기존 기록이다.

현재 목표: **Xabi Alonso Tactical System Intelligence**. 이번 구현은 Milestone 1의 Alonso-Leverkusen 실제 데이터 확대 및 Wirtz event-only Tactical Role MVP다. Neural Network, System Fit 및 Palmer 비교는 구현하지 않는다.

- [실제 Wirtz 보고서](outputs/wirtz_alonso_role_mvp/role_summary.md)
- [계산 정의와 한계](docs/tactical_features_mvp.md)
- [시즌별 실제 데이터 감사](outputs/wirtz_alonso_role_mvp/available_data_audit.json)

재실행 (공식 카탈로그에서 확인된 2023/24 전체 34경기):

```bash
.venv/bin/python -m src.data.ingestion --competition 9 --season 2023/2024 --match-limit 34
.venv/bin/python -m src.analysis.audit_alonso_data
.venv/bin/python -m src.analysis.wirtz_role_mvp
.venv/bin/python -m unittest discover -s tests -q
```

캐시 확보 후 ingestion 명령에 `--offline`을 추가하면 동일 원본에서 재생성한다. 분석은 검증된 processed snapshot과 raw event qualifier를 사용한다. 기존 네 Parquet 테이블·스키마는 유지하고 feature CSV/PNG는 outputs에 생성한다. 360 결합 오류는 manifest에 기록하고 event ingestion은 계속한다.

장기 원칙: 실제 결과 우선, baseline 우선, event/360 결측 분리, 다경기·다선수 관측으로 시스템 검증, 설명 가능한 similarity, context 고려, 인과 주장 금지, 기존 pipeline 재사용. 다음 milestone은 사용자 검토 후에만 시작한다.

기존 Phase 3 기록:

- [현재 ingestion 실행·데이터 범위·제약](docs/data_ingestion.md)
- [Phase 2 스키마 및 리뷰](docs/dataset_schema.md)
- [Phase 1 조사 기록](docs/phase1-data-strategy.md) — 당시 미확인 항목의 후속 확인은 ingestion 문서 참고

Python 3.11+ 및 venv 사용; Python 3.13.5에서 검증했다. Phase 3 runtime 의존성은 pyarrow 하나다.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

아래는 기존 Phase 3의 2경기 검증 명령이다. 실행하면 전체 snapshot을 2경기로 교체하므로 현재 전체 데이터 재생성에는 위 34경기 명령을 사용한다. 기본 실행은 공식 competitions.json에서 season ID를 조회한다.

```bash
.venv/bin/python -m src.data.ingestion --source statsbomb --competition 9 --season 2023/2024 --match-limit 2
```

기존 Phase 3의 두 경기 slice를 재현하는 명령:

```bash
.venv/bin/python -m src.data.ingestion --offline --match-limit 2 --match-id 3895052 --match-id 3895292
```

`data/raw/`에 원본과 URL·시간·SHA-256 receipt, `data/processed/`에 네 개의 typed Parquet, manifest, 품질 보고서를 저장한다. 처리 결과는 같은 slice를 교체하며 누적 append하지 않는다. raw/interim/processed 및 기존 availability 자료는 Git에서 제외한다. 작은 테스트 fixture는 명백히 synthetic이며 실제 경기 데이터에 섞이지 않는다.

**Data source: StatsBomb Open Data.** 공식 User Agreement의 연구·비상업 용도를 준수한다. 원본 및 처리 데이터를 외부에 재배포하지 않는다. 분석 공개 시 StatsBomb 출처와 브랜드 로고를 표시해야 한다. 문서는 resource centre에 사용자 관심 등록을 요청하며, 이 작업에서 사용자의 개인정보를 등록·전송하지 않았다. [공식 라이선스](https://github.com/statsbomb/open-data/blob/master/LICENSE.pdf), [출처 및 로고 안내](https://github.com/statsbomb/open-data/blob/master/README.md).

FBref 자동 수집은 구현하지 않았다. 고급 데이터 삭제 공지와 현행 ML 관련 이용 제한 때문에 이 프로젝트의 fallback으로 사용 가능하다고 간주하지 않는다. 로컬 집계 adapter도 별도의 이용 권한·원출처 확인을 전제로 한다.
