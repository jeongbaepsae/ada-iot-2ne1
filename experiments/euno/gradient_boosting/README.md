# Gradient Boosting 떨림 분류기 (euno)

과제 1 제출물. 담당 모델은 **Gradient Boosting** 이며 LightGBM을 주 모델로,
XGBoost를 같은 조건의 대조군으로 함께 평가한다. Random Forest는 사용하지 않는다.

## 1. 모델과 전처리

### 전처리

전처리는 `scripts/run_baseline_analysis.py`를 그대로 import해서 사용한다. 새로
구현한 부분이 없으므로 기존 Logistic Regression / RBF-SVM / Random Forest 결과와
숫자를 직접 비교할 수 있다.

| 항목 | 값 |
| --- | --- |
| 리샘플링 | 선형 보간으로 50 Hz 균일 격자 |
| window | 3초 (150 sample), 50% overlap |
| window 제외 규칙 | 원본 timestamp 간격이 100 ms를 넘는 구간을 포함하면 제외 |
| 입력 센서 | 가속도계 3축 + 자이로스코프 3축 |
| window feature | 축별 평균 제거 후 3축 norm에 대한 RMS, std, MAD, jerk RMS, zero-crossing rate + Welch PSD 기반 스펙트럼 feature |
| 스펙트럼 feature | 3–12 Hz log power, dominant Hz, peak ratio, spectral entropy, tremor/total ratio, 3–6 / 6–9 / 9–12 Hz 대역 비율 |
| recording 집계 | window feature의 median과 IQR |

분류는 **recording 단위**로 수행한다. 따라서 같은 recording의 window가 train과
test로 나뉘는 일이 구조적으로 발생하지 않는다.

feature set 두 가지를 모두 평가한다.

- `B1_time`: 시간 영역 feature만 사용 (10개)
- `B2_time_frequency`: 시간 + 주파수 feature 전체 사용 (52개)

### 모델

하이퍼파라미터는 **사전에 고정**했고 어떤 test fold에서도 튜닝하지 않았다.
LOSO fold당 학습 recording이 약 170~200개뿐이므로 얕은 트리와 낮은 learning rate,
row/column subsampling을 보수적 기본값으로 잡았다.

| 파라미터 | LightGBM | XGBoost |
| --- | --- | --- |
| n_estimators | 300 | 300 |
| learning_rate | 0.05 | 0.05 |
| 트리 크기 | num_leaves 15, max_depth 4 | max_depth 3 |
| 최소 leaf 크기 | min_child_samples 5 | min_child_weight 1.0 |
| subsample | 0.8 (매 iteration) | 0.8 |
| colsample_bytree | 0.8 | 0.8 |
| reg_lambda | 1.0 | 1.0 |
| 클래스 가중치 | balanced | 기본값 (라벨이 110/110로 균형) |
| random_state | 42 | 42 |

트리 모델은 스케일에 불변하지만 기존 baseline과 pipeline 형태를 맞추기 위해
`StandardScaler`를 앞에 둔다. scaler는 fold의 train 부분에만 fit된다.

### 평가

- **LOSO**: 참가자 6명(BIBI, anna, euno, march, mu, seojin)에 대해 사람 단위로
  한 명씩 test.
- **cross-dataset**: `dataset_a → dataset_b`, `dataset_b → dataset_a` 양방향.
- 지표: balanced accuracy, sensitivity, specificity, macro F1 (추가로 AUROC, AUPRC,
  혼동행렬 counts).
- 판정 임계값은 확률 0.5 고정.

## 2. 실행 방법

macOS에서 LightGBM과 XGBoost는 OpenMP 런타임이 필요하다. 먼저 설치한다.

```bash
brew install libomp
```

이후 저장소 루트에서 다음을 실행한다.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install lightgbm==4.7.0 xgboost==3.4.1
MPLCONFIGDIR=/tmp/ada_iot_mpl .venv/bin/python experiments/euno/gradient_boosting/train.py
```

`results/recording_features_3s.csv`가 없으면 스크립트가 `data/manifest.csv`를 읽어
원본 데이터에서 feature를 다시 생성한다. 그림 생성을 건너뛰려면 `--no-plots`를
붙인다.

검증에 사용한 버전: Python 3.12.14, numpy 2.3.2, pandas 2.3.1, scipy 1.16.1,
scikit-learn 1.7.1, lightgbm 4.7.0, xgboost 3.4.1.

### 생성물

| 파일 | 내용 |
| --- | --- |
| `results.csv` | fold별 전체 지표 (LOSO 6 + cross-dataset 2) × 모델 2 × feature set 2 |
| `predictions.csv` | recording 단위 예측 확률과 정오 여부 |
| `misclassified.csv` | 오분류 사례만 추린 표 (margin 오름차순) |
| `feature_importance.csv` | B2 feature set의 fold 평균 정규화 importance |
| `summary_comparison.csv` | 기존 baseline을 포함한 모델별 평균 지표 |
| `summary.json` | 요약 |
| `model_comparison.png` | 기존 baseline 대비 막대그래프 |
| `loso_per_subject.png` | 참가자별 LOSO 성능 |

## 3. 결과

### LOSO 참가자별 balanced accuracy

| 참가자 | LightGBM B1 | LightGBM B2 | XGBoost B1 | XGBoost B2 |
| --- | ---: | ---: | ---: | ---: |
| BIBI | 1.000 | 1.000 | 1.000 | 1.000 |
| anna | 1.000 | 1.000 | 1.000 | 1.000 |
| euno | 1.000 | 1.000 | 1.000 | 1.000 |
| **march** | **0.800** | **1.000** | **0.700** | **0.700** |
| mu | 1.000 | 1.000 | 1.000 | 1.000 |
| seojin | 1.000 | 1.000 | 1.000 | 1.000 |
| **평균** | **0.967** | **1.000** | **0.950** | **0.950** |

### cross-dataset balanced accuracy

| 방향 | LightGBM B1 | LightGBM B2 | XGBoost B1 | XGBoost B2 |
| --- | ---: | ---: | ---: | ---: |
| dataset_a → dataset_b | 0.988 | 1.000 | 1.000 | 1.000 |
| dataset_b → dataset_a | 0.979 | 1.000 | 0.957 | 0.957 |
| **평균** | **0.983** | **1.000** | **0.979** | **0.979** |

## 4. 기존 Random Forest 및 다른 baseline과의 비교

`B2_time_frequency` 기준 (평균값).

| 모델 | LOSO BA | LOSO 표준편차 | LOSO sens. | LOSO spec. | LOSO macro F1 | cross-dataset BA |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Logistic Regression | 0.9750 | 0.0612 | 0.950 | 1.000 | 0.9744 | 0.9893 |
| RBF-SVM | 0.9917 | 0.0204 | 1.000 | 0.983 | 0.9916 | 0.9768 |
| Random Forest (기존) | 0.9917 | 0.0204 | 0.983 | 1.000 | 0.9916 | 0.9902 |
| **LightGBM (본 과제)** | **1.0000** | **0.0000** | **1.000** | **1.000** | **1.0000** | **1.0000** |
| XGBoost (본 과제) | 0.9500 | 0.1225 | 0.900 | 1.000 | 0.9451 | 0.9786 |

`B1_time` 기준.

| 모델 | LOSO BA | cross-dataset BA |
| --- | ---: | ---: |
| Logistic Regression | 0.9667 | 0.9705 |
| RBF-SVM | 0.9750 | 0.9705 |
| Random Forest (기존) | 0.9792 | 0.9804 |
| LightGBM (본 과제) | 0.9667 | 0.9830 |
| XGBoost (본 과제) | 0.9500 | 0.9786 |

요약하면 다음과 같다.

- LightGBM은 B2 feature set에서 LOSO와 cross-dataset 모두 완전 분류를 달성해
  Random Forest(0.9917 / 0.9902)를 근소하게 앞선다.
- 같은 gradient boosting 계열이라도 XGBoost는 B2에서도 Random Forest보다 낮다.
  즉 "gradient boosting이 더 낫다"가 아니라 **이 데이터 크기에서는 모델 간 차이가
  참가자 한 명의 recording 몇 개에 의해 결정된다**고 읽는 것이 정확하다.
- 220개 recording, 참가자 6명 규모에서 0.99와 1.00의 차이는 **오분류 recording
  1~2개 차이**에 불과하므로 순위 자체를 결론으로 삼으면 안 된다.

## 5. 오분류 사례와 한계

### 오분류가 한 명에게 전부 몰려 있다

전체 오분류 32건(= recording × fold × 모델 × feature set 조합 기준)은 **예외 없이
참가자 `march`의 tremor recording에 대한 false negative**다. false positive는
cross-dataset에서 `dataset_b:mu_still_18` 단 1건뿐이다. 즉 모든 모델이 "떨림이
아닌 것을 떨림이라 하는" 오류는 거의 내지 않고, "약한 떨림을 놓치는" 오류만 낸다.

### 원인: march의 모사 떨림 강도가 구조적으로 낮다

recording 단위 feature의 참가자별 median은 다음과 같다.

| 참가자 | tremor acc RMS | tremor acc 3–12 Hz log power | tremor tremor/total ratio |
| --- | ---: | ---: | ---: |
| BIBI | 0.2025 | -1.449 | 0.881 |
| anna | 0.2349 | -1.454 | 0.869 |
| mu | 0.2215 | -1.389 | 0.928 |
| seojin | 0.1838 | -1.637 | 0.910 |
| euno | 0.1212 | -2.031 | 0.808 |
| **march** | **0.0750** | **-2.597** | **0.560** |

march의 모사 떨림은 다른 참가자의 3분의 1 수준 진폭이고 3–12 Hz 대역 집중도도
가장 낮다. 반면 march의 non-tremor 신호는 다른 참가자와 차이가 없다. LOSO에서
march를 test로 두면 학습 데이터에 "약한 떨림" 사례가 남지 않으므로, 모델이 다른
참가자 기준으로 학습한 진폭 경계 아래에 march의 tremor가 놓인다.

### 중요한 단서: 순위는 완벽하지만 임계값이 틀렸다

`march` fold를 포함해 **모든 fold의 AUROC가 1.000** 이다. 즉 오분류가 난 fold에서도
모델은 march의 tremor recording 전부에 march의 non-tremor recording 전부보다 높은
확률을 부여했다. 실패한 것은 분류 능력이 아니라 **고정된 0.5 임계값**이다.
예를 들어 XGBoost B2의 march fold에서 놓친 6개 recording의 확률은 0.037~0.060이고,
같은 fold의 non-tremor는 그보다 더 낮다.

실무적으로는 참가자별 기준선 보정(예: 안정 상태 구간으로 개인 임계값 조정)이나
train fold에서만 임계값을 고르는 절차가 다음 단계로 필요하다. 이번 과제에서는
평가 규칙 통일을 위해 0.5 고정을 유지했다.

### 주파수 feature의 기여

B1 → B2로 갈 때 LightGBM의 march fold가 0.800에서 1.000으로 올라간다. 반면
XGBoost는 0.700에서 그대로다. LightGBM의 B2 importance 상위는
`acc__log_power_3_12__median`(0.541), `acc__jerk_rms__median`(0.321)로 스펙트럼
feature가 1순위지만, XGBoost는 `acc__mad__median`(0.438) 같은 진폭 feature를 먼저
쓴다. 저장소의 연구 질문("주파수 정보를 명시적으로 사용하면 subject-independent
성능이 개선되는가")에 대해, 이번 결과는 **개선되지만 모델이 그 feature를 실제로
선택할 때만 그렇다**는 조건부 근거를 제공한다. 다만 근거는 참가자 1명 fold이므로
약하다.

### 그 밖의 한계

- 참가자가 6명뿐이라 LOSO 평균의 표준편차가 fold 하나에 지배된다. LightGBM B2의
  표준편차 0.0000은 "안정적"이라는 뜻이 아니라 "6개 fold가 모두 포화됐다"는 뜻이다.
- 두 데이터셋 모두 건강한 참가자의 **자발적 모사 떨림**이다. 실제 환자의 병적
  떨림에 대한 성능은 이 결과로 주장할 수 없다.
- non-tremor 조건이 대체로 정지 상태라 acc RMS 차이가 매우 커서 문제 자체가 쉽다.
  걷기, 물건 들기 같은 능동 동작이 non-tremor에 포함되면 난이도가 크게 달라질
  것으로 예상한다.
- 하이퍼파라미터를 고정했으므로 nested CV 기반 튜닝 결과는 아니다. 다만 이 규모에서
  test fold를 본 튜닝은 낙관적 편향을 만들므로 고정이 더 안전한 선택이라고 판단했다.
