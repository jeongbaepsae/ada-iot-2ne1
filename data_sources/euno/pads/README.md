# PADS — Parkinson's Disease Smartwatch dataset (euno)

과제 2 제출물. 현재 저장소에 없는 오픈소스 떨림 관련 데이터셋으로 **PADS**를
선정했다.

## 1. 데이터셋 이름과 출처

| 항목 | 내용 |
| --- | --- |
| 이름 | PADS — Parkinsons Disease Smartwatch dataset, v1.0.0 |
| 공개처 | PhysioNet |
| URL | https://physionet.org/content/parkinsons-disease-smartwatch/1.0.0/ |
| DOI | https://doi.org/10.13026/m0w9-zx22 |
| 공개일 | 2024년 3월 25일 |
| 논문 | Varghese J. et al., "Machine Learning in the Parkinson's disease smartwatch (PADS) dataset", *npj Parkinsons Disease* 10, 9 (2024). https://doi.org/10.1038/s41531-023-00625-7 |
| 전체 용량 | 약 1.4 GB (압축 해제 기준) |

## 2. 라이선스와 재배포

- 라이선스: **Creative Commons Attribution-NonCommercial-ShareAlike 4.0
  International (CC BY-NC-SA 4.0)**
- 재배포: 출처 표기 + 동일 라이선스 + **비영리** 조건을 지키면 가능하다.
- **하지만 이 저장소에는 원본 데이터를 커밋하지 않는다.** 두 가지 이유가 있다.
  1. 1.4 GB는 git 저장소에 넣기에 너무 크다.
  2. 현재 저장소는 자체 라이선스가 명시되어 있지 않다. ShareAlike 조건이 붙은
     데이터를 라이선스 없는 저장소에 섞으면 이후 공개 조건이 꼬인다.
- 따라서 **다운로드 링크 + 준비 스크립트**만 제출한다. 변환 결과는
  `.gitignore`에 이미 포함된 `data/processed/` 아래에 생성되므로 실수로
  커밋될 위험이 없다.
- 논문/발표에 사용할 경우 위 논문과 PhysioNet DOI를 모두 인용해야 한다.

## 3. 규모, 라벨, 센서, sampling rate

### 참가자와 진단 라벨

전체 **469명**, 총 5,159개 측정 단계. `preprocessed/file_list.csv`에서 집계한
진단 분포는 다음과 같다.

| condition | 인원 | 데이터셋 label 값 |
| --- | ---: | --- |
| Parkinson's | 276 | 1 |
| Healthy | 79 | 0 |
| Other Movement Disorders | 60 | 2 |
| Essential Tremor | 28 | 2 |
| Atypical Parkinsonism | 15 | 2 |
| Multiple Sclerosis | 11 | 2 |

성별은 남 281 / 여 188, 손잡이는 오른손 437 / 왼손 32이다.

### 센서

| 항목 | 값 |
| --- | --- |
| 기기 | Apple Watch Series 4, **양쪽 손목에 각 1대** |
| 센서 | 가속도계 3축 + 자이로스코프 3축 |
| sampling rate | 100 Hz |
| 단위 | 가속도 g, 각속도 rad/s |
| 가속도 특성 | **중력 성분이 제거된 user acceleration** (아래 7절 참고) |

### recording 구성

참가자 1명당 **11개 동작 과제 × 양 손목 = 22개 recording**.

| 과제 | 성격 | 길이 |
| --- | --- | --- |
| Relaxed | 안정 | 2048 sample = 20.48초 |
| RelaxedTask | 안정 + 인지 부하 | 2048 sample = 20.48초 |
| StretchHold | 자세 유지 | 1024 sample = 10.24초 |
| LiftHold | 자세 유지 | 1024 sample = 10.24초 |
| HoldWeight | 부하 유지 | 1024 sample = 10.24초 |
| PointFinger | 운동 | 1024 sample = 10.24초 |
| DrinkGlas | 운동 | 1024 sample = 10.24초 |
| CrossArms | 운동 | 1024 sample = 10.24초 |
| TouchIndex | 운동 | 1024 sample = 10.24초 |
| TouchNose | 운동 | 1024 sample = 10.24초 |
| Entrainment | entrainment 검사 | 2048 sample = 20.48초 |

참가자 ID(`001`~`469`), 과제, 손목이 모두 파일명과 메타데이터로 구분되므로
사람 단위 LOSO 분할이 가능하다.

## 4. 파일 형식과 주요 column

```text
pads_dataset/
├── movement/
│   ├── observation_001.json ... observation_469.json   # 채널 정의와 파일 링크
│   └── timeseries/
│       └── <ID>_<Task>_<Wrist>.txt                     # 예: 001_Relaxed_LeftWrist.txt
├── patients/patient_001.json ...                       # 진단, 나이, 성별, 손잡이
├── questionnaire/                                      # 비운동 증상 설문 30문항
├── preprocessed/
│   ├── file_list.csv                                   # 469명 메타데이터 요약
│   └── movement/                                       # 132채널 binary (전처리본)
└── scripts/                                            # 저자 제공 전처리 코드
```

`timeseries/*.txt`는 헤더 없는 CSV이고, column 순서는
`movement/observation_*.json`의 `channels` 필드에서 확인했다.

| # | channel | 단위 |
| ---: | --- | --- |
| 1 | Time | s |
| 2 | Accelerometer_X | g |
| 3 | Accelerometer_Y | g |
| 4 | Accelerometer_Z | g |
| 5 | Gyroscope_X | rad/s |
| 6 | Gyroscope_Y | rad/s |
| 7 | Gyroscope_Z | rad/s |

`patients/patient_*.json`의 주요 field는 `condition`(진단명),
`disease_comment`(자유 기술 임상 소견), `age`, `age_at_diagnosis`, `gender`,
`handedness`, `effect_of_alcohol_on_tremor`이다.

## 5. 다운로드 및 준비 방법

### 준비 스크립트 (권장)

필요한 파일만 내려받아 현재 저장소 schema로 변환한다.

```bash
# 4명만 받아보는 smoke test (수 MB)
.venv/bin/python data_sources/euno/pads/download_or_prepare.py --limit-subjects 4

# 다운로드 없이 선정 코호트만 확인
.venv/bin/python data_sources/euno/pads/download_or_prepare.py --dry-run

# strict 코호트 전체 (참가자 160명, recording 1600개)
.venv/bin/python data_sources/euno/pads/download_or_prepare.py
```

표준 라이브러리와 이미 설치된 패키지만 사용하므로 추가 의존성은 없다.

주요 옵션.

| 옵션 | 기본값 | 설명 |
| --- | --- | --- |
| `--cohort {strict,broad}` | `strict` | 라벨 도출 규칙 (6절) |
| `--tasks {rest_postural,kinetic,all}` | `rest_postural` | 내보낼 동작 과제 |
| `--wrists LeftWrist RightWrist` | 양쪽 | 손목 선택 |
| `--limit-subjects N` | 없음 | 클래스 균형을 맞춰 N명만 |
| `--drop-initial-seconds` | `0.5` | 워치 진동 알림 구간 제거 (저자 권고) |
| `--source-dir PATH` | 없음 | 이미 받아둔 로컬 복사본에서 변환 |
| `--output-dir PATH` | `data/processed/dataset_c_pads` | 출력 위치 |

### 전체 원본 내려받기

```bash
wget -r -N -c -np https://physionet.org/files/parkinsons-disease-smartwatch/1.0.0/
```

이후 `--source-dir`로 변환하면 HTTP 요청 없이 처리된다.

## 6. 공통 CSV schema 변환

### 라벨 도출 — 가장 주의해야 할 부분

**PADS에는 recording 단위 tremor / non-tremor 라벨이 없다.** 있는 것은
참가자 단위 임상 진단뿐이다. 따라서 현재 저장소의 이진 라벨로 쓰려면 규칙을
명시적으로 만들어야 하고, 그 규칙이 곧 약한 라벨(weak label)이 된다.
스크립트는 두 가지 규칙을 제공하고 선택 결과를 manifest의 `label_source` column에
기록한다.

| 규칙 | tremor | non_tremor | 제외 |
| --- | --- | --- | --- |
| `strict` (기본) | Parkinson's 또는 Essential Tremor 이면서 `disease_comment`에 tremor 표현이 있는 참가자 → **81명** | Healthy → **79명** | Other Movement Disorders, Atypical Parkinsonism, Multiple Sclerosis, 그리고 tremor 표현이 없는 PD(주로 akinetic-rigid type) |
| `broad` | 모든 Parkinson's + Essential Tremor → **304명** | Healthy → **79명** | 위 3개 진단군 |

`strict`를 기본으로 둔 이유는 두 가지다.

1. `IPS akinetic-rigid type`처럼 떨림이 주 증상이 아닌 파킨슨병 환자를 tremor로
   넣으면 라벨 자체가 틀린다. `disease_comment`에 `tremordominant`,
   `Essential Tremor` 같은 표현이 있는 경우만 양성으로 본다.
2. 결과적으로 81 대 79로 클래스가 거의 균형을 이룬다.

또한 기본값은 **안정·자세 유지 과제 5종**(`Relaxed`, `RelaxedTask`,
`StretchHold`, `LiftHold`, `HoldWeight`)만 내보낸다. `DrinkGlas`나 `TouchNose`
같은 운동 과제는 의도된 큰 동작이 신호를 지배해서 현재 저장소의 non-tremor
(대부분 정지 상태) 정의와 충돌하기 때문이다.

### 신호 변환

| 현재 저장소 column | PADS 원본 | 변환 |
| --- | --- | --- |
| `elapsed_ms` | `Time` [s] | `(t - t0) * 1000`, 0부터 시작하도록 재기준 |
| `acc_x_g`, `acc_y_g`, `acc_z_g` | `Accelerometer_X/Y/Z` [g] | 그대로 |
| `gyro_x_dps`, `gyro_y_dps`, `gyro_z_dps` | `Gyroscope_X/Y/Z` [rad/s] | `× 180/π` |
| `angle_x_deg`, `angle_y_deg`, `angle_z_deg` | 없음 | **빈 값** |

PADS에는 자세 추정 각도가 없다. 다만 `scripts/run_baseline_analysis.py`는
`elapsed_ms`와 가속도·자이로 6축만 사용하므로(`SENSOR_COLUMNS` 참고) 현재 모든
실험에 대해 무손실이다. 각도 column을 채우려면 자이로 적분이 필요한데 drift가
생기므로 비워 두는 쪽을 택했다.

`--drop-initial-seconds 0.5`는 "과제 시작 알림 진동이 앞 0.5초에 섞인다"는 저자
권고를 반영한 것이다.

### 출력물

```text
data/processed/dataset_c_pads/
├── manifest_dataset_c.csv
├── pads_001_still/pads_001_Relaxed_LeftWrist.csv
├── pads_001_still/pads_001_Relaxed_RightWrist.csv
└── pads_005_tremor/...
```

`manifest_dataset_c.csv`는 기존 `data/manifest.csv`와 같은 column
(`recording_id`, `dataset_id`, `subject_id`, `label`, `relative_path`, `n_rows`,
`duration_s`, `median_dt_ms`, `min_dt_ms`, `max_dt_ms`, `non_increasing_steps`,
`gaps_over_100ms`)에 더해 추적용 column
(`pads_condition`, `pads_disease_comment`, `pads_task`, `pads_wrist`,
`label_source`)을 덧붙인다.

좌우 손목은 별개 recording이지만 `subject_id`가 같으므로, 사람 단위 LOSO를
쓰는 한 같은 사람의 좌우 손목이 train과 test로 갈라지지 않는다.

### 기존 파이프라인에 붙일 때 필요한 변경

`scripts/build_manifest.py`의 `parse_identity()`는 `dataset_a` / `dataset_b`의
폴더 규칙만 알고 있다. 준비 스크립트는 `dataset_b`와 같은
`<subject>_still` / `<subject>_tremor` 규칙으로 폴더를 만들고 manifest도 직접
생성하므로, 공용 스크립트를 당장 고칠 필요는 없다. dataset_c를
`data/raw/`로 승격하기로 팀이 합의하면 `parse_identity()`에 `dataset_c` 분기를
한 줄 추가하면 된다.

## 7. 데이터 품질과 장단점

### 검증한 내용

참가자 4명(healthy 2, tremor 2)으로 smoke test를 실행해 변환본을 기존
feature 파이프라인에 그대로 통과시켰다.

- recording 40개에서 **유효 window 312개, 제외 window 0개**. 100 Hz 균일
  timestamp라 간격 결함이 없다. `dataset_b`가 jitter와 gap 때문에 window를
  버리는 것과 대조적이다.
- 라벨별 recording 단위 feature 중앙값:

| label | acc RMS | acc 3–12 Hz log power | acc dominant Hz | tremor/total ratio | gyro RMS |
| --- | ---: | ---: | ---: | ---: | ---: |
| non_tremor (healthy) | 0.0087 | -4.55 | 4.00 | 0.441 | 1.43 |
| tremor (PD/ET) | 0.0745 | -2.30 | 6.67 | 0.918 | 16.45 |

현재 저장소의 모사 떨림과 같은 방향으로 분리되며, 크기 차이도 비슷한 수준이다.

### 장점

- **실제 환자 데이터.** 현재 저장소는 전부 건강한 참가자의 자발적 모사 떨림이다.
  PADS를 붙이면 "모사 떨림에서 학습한 모델이 실제 병적 떨림으로 전이되는가"라는
  질문을 처음으로 던질 수 있다.
- **참가자 규모가 78배.** 현재 6명 → PADS strict 코호트만 160명. LOSO 결과의
  표준편차가 fold 하나에 지배되는 현재 문제가 크게 완화된다.
- **동일 센서 구성.** 손목 착용 가속도계 + 자이로, 그리고 Apple Watch라는 점이
  `docs/APPLE_WATCH_ROADMAP_KO.md`의 1번 트랙과 정확히 일치한다.
- **타이밍 품질이 좋다.** 100 Hz 균일 격자, gap 없음.
- **표준화된 과제 프로토콜.** 안정/자세/운동 과제가 분리돼 있어 조건별 성능을
  나눠 볼 수 있다.
- **대조군이 명확하다.** Healthy 79명과 essential tremor 28명이 함께 있어,
  "떨림 여부"와 "파킨슨병 여부"를 구분해 다룰 수 있다.

### 한계와 주의점

1. **recording 단위 라벨이 없다.** 6절의 도출 규칙은 약한 라벨이다. 특히
   안정 과제에서도 환자가 실제로 떨고 있었는지는 보장되지 않는다. 논문에서
   "tremor detection"으로 쓰려면 이 점을 반드시 명시해야 한다.
2. **가속도에 중력이 없다.** PADS의 가속도 크기 평균은 약 0.004–0.15 g이고,
   현재 저장소 데이터는 약 1.0 g다. PADS는 중력이 제거된 user acceleration이다.
   다행히 `window_features()`가 window마다 축별 평균을 빼기 때문에 파생 feature는
   비교 가능하지만, **원시 신호를 그대로 입력하는 모델(1D CNN 등)을 만들 때는
   반드시 중력 제거를 통일해야 한다.**
3. **떨림 주파수 대역이 다르다.** smoke test 기준 PADS 환자의 dominant frequency는
   약 5.7–7.3 Hz인데, 현재 저장소의 모사 떨림은 참가자 중앙값이 약 6.0–11.3 Hz다.
   실제 파킨슨 떨림(4–6 Hz)과 본태성 떨림(4–12 Hz)의 알려진 범위를 생각하면,
   **모사 떨림이 실제 떨림보다 빠르게 재현되고 있을 가능성**이 있다. 이는 현재
   모델의 외적 타당도에 직접 영향을 주는 문제이므로 별도로 확인할 가치가 있다.
4. **non-tremor의 의미가 다르다.** 현재 저장소의 non-tremor는 "가만히 있기"이고,
   PADS의 non_tremor는 "건강한 사람이 과제를 수행 중"이다. 후자가 더 어렵고
   현실적이다. 두 데이터를 합쳐 학습하면 난이도가 섞이므로 cross-dataset 평가로
   분리해 보는 편이 해석이 깨끗하다.
5. **클래스 불균형.** 전체 469명 기준 PD가 276명으로 과반이다. strict 코호트는
   81/79로 균형을 맞췄지만 broad 코호트(304/79)를 쓰면 balanced accuracy 등
   불균형에 강한 지표가 필수다.
6. **비영리 라이선스.** CC BY-NC-SA이므로 상업적 활용 계획이 생기면 이 데이터로
   학습한 모델의 배포 조건을 다시 검토해야 한다.
7. **환자 데이터라는 점을 기록에 남겨야 한다.** 현재 저장소 README는 "임상 진단
   데이터가 아니다"라고 명시하고 있다. PADS를 추가하면 그 문장을 데이터셋별로
   나누어 다시 써야 한다.

### 다음 단계 제안

- strict 코호트 전체를 내려받아 `dataset_c`로 두고, 기존 B1/B2 feature와
  Random Forest / LightGBM으로 `dataset_a+b → dataset_c` 전이 성능을 측정한다.
  모사 떨림 학습이 실제 떨림에 얼마나 전이되는지가 핵심 결과가 된다.
- 3번 한계(주파수 대역 불일치)를 먼저 정량 확인한다. 이것이 사실이면 향후 데이터
  수집 프로토콜에서 모사 떨림 속도를 조정해야 한다.
