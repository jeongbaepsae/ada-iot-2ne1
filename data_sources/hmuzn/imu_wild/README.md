# IMU-Wild: 실제 환경 파킨슨 떨림 데이터

## 출처와 이용 조건

- 공식 데이터: <https://doi.org/10.5281/zenodo.3519213>
- 논문: Papadopoulos et al., *Detecting Parkinsonian Tremor from IMU Data
  Collected In-The-Wild using Deep Multiple-Instance Learning*, IEEE JBHI,
  <https://doi.org/10.1109/JBHI.2019.2961748>
- 라이선스: Creative Commons Attribution 4.0 (CC BY 4.0). 출처 표시 후 연구 및
  재배포가 가능하지만 원본은 크기와 provenance 보존을 위해 저장소에 커밋하지 않는다.

## 데이터 개요

31명의 파킨슨병 환자와 14명의 건강 대조군, 총 45명이 개인 스마트폰으로 통화할
때 수집한 실제 환경(in-the-wild) 3축 가속도 시계열이다. 한 session은 최대 75초이며
사람마다 여러 session이 있다. pickle 안의 각 subject dictionary에는
`subject_id`, `subject_sessions`(각각 N×4: timestamp, x, y, z),
`session_datetimes`, `annotation`이 있다. `annotation.sp_expert`는 신호처리 전문가가
UPDRS와 신호를 함께 검토한 사람 단위 이진 떨림 라벨이다. 임상 UPDRS 항목과
`pd_status`도 제공된다.

중요: `sp_expert`는 session별 라벨이 아니라 **사람 단위의 coarse label**이다.
떨림은 간헐적이므로 tremor subject의 모든 session/window를 양성으로 간주하면
label noise가 생긴다. 따라서 현재 팀 데이터와 단순 합쳐 window 분류를 해서는 안
되며, subject를 bag으로 취급하는 multiple-instance 평가나 외부 검증에 사용해야 한다.
또한 gyroscope가 없으므로 공통 6축 모델에는 결측 센서 전략이 필요하다.

## 준비 방법

1. DOI의 공식 페이지에서 pickle을 내려받고 공식 설명/체크섬을 확인한다.
2. pickle은 역직렬화 시 코드를 실행할 수 있으므로 공식 파일만 사용한다.
3. 원본을 git 밖에 두고 다음과 같이 공통 CSV로 변환한다.

```bash
.venv/bin/python data_sources/hmuzn/imu_wild/download_or_prepare.py \
  /trusted/path/to/official.pkl /tmp/imu_wild_converted \
  --time-unit s --acc-unit m_s2
```

출력 CSV column은 `elapsed_ms,acc_x_g,acc_y_g,acc_z_g`이며 별도 `manifest.csv`에
participant/session, tremor label, label scope, PD/UPDRS 일부를 기록한다. 위 단위 값은
예시일 뿐이며, **다운로드에 포함된 공식 README에서 단위를 확인해 옵션으로 명시**해야
한다. `m_s2`를 선택하면 표준중력 9.80665로 나눠 g로 변환한다.

## 장점과 한계

팀의 건강인 모사 떨림과 달리 실제 환자·실생활·여러 스마트폰 조건의 domain shift를
검증할 수 있다. 반면 기기/착용 위치가 Apple Watch와 다르고, sampling jitter,
가속도 단위, session 수 불균형, 사람 단위 라벨 때문에 직접 통합 학습 전 별도 품질
검사와 MIL 설계가 필요하다.
