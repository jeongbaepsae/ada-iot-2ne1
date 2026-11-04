# PD-TD 떨림 3D 뷰어

PADS 공개 데이터에서 떨림우세형 파킨슨(PD-TD)과 건강 대조군의 손목 IMU를
3차원으로 비교하고, 현장에서 직접 측정까지 할 수 있는 단일 페이지 도구입니다.

- `index.html` — 뷰어 본체 (데이터 내장)
- `field.js` — 현장 측정 콘솔 (DeviceMotion)

빌드 과정은 없습니다. 외부 의존은 Plotly(CDN)와 Google Fonts 뿐입니다.

담긴 것: 가속도·자이로 3차원 점 분포(개인별 / 군별 비교 / 군 전체 겹쳐보기),
2–12 Hz 필터 전·후 비교, 시간 구간 조절과 시간순 쌓기,
임상 표준 그림 5종(PSD · 떨림 파형 · 스펙트로그램 · 군별 진폭 분포 · 주파수×진폭 평면),
현장 측정 콘솔.

생성 스크립트는 https://github.com/jeongbaepsae/iOT-tremor-dataset 쪽
`analysis/` 에 있습니다 (`pads_cohort.py` → `export_cohort_3d.py` → `build_cohort_viewer.py`).

## 현장 측정에 대하여

`DeviceMotion` 을 쓰므로 **HTTPS 환경에서만** 센서가 동작합니다. GitHub Pages 는
HTTPS 라 그대로 됩니다. CSV 불러오기와 분석은 어디서든 동작합니다.

저장 포맷: `elapsed_ms, acc_x_g…z(중력 포함), lin_x_g…z(중력 제외), gyro_x_dps…z`

중력을 포함한 열을 함께 남기는 이유는 중력 방향이 연직이라는 절대 기준을 주기
때문입니다. PADS 는 중력을 빼고 배포해서 손목 자세를 복원할 기준이 없습니다.

## 데이터 출처와 라이선스

PADS — Parkinson's Disease Smartwatch dataset v1.0.0 (PhysioNet).
Varghese J, Brenner A, Plagwitz L, van Alen C, Fujarski M, Warnecke T.
*npj Parkinsons Dis* 2024;10:9. DOI [10.13026/m0w9-zx22](https://doi.org/10.13026/m0w9-zx22)

원 데이터와 이 저장소에 담긴 파생물은 모두
**[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)** 로 배포됩니다
— 출처 표시 · 비영리 · 동일조건 변경허락.

내장된 값은 원본을 50 Hz 로 솎아내고 대역 필터와 스펙트럼을 계산한 파생
데이터입니다 (PD-TD 10명 + 건강 대조군 10명, Relaxed·TouchNose, 양 손목).

## 주의

연구용 도구입니다. 진단이나 치료 판단에 사용하지 마세요.
표시되는 값은 모두 측정값에서 계산한 것입니다. 보간으로 손 경로를 그리던
3D 인체 애니메이션은 접촉 검출 검증에 실패해 제거했습니다.
