# 📊 DORA 주간 보고서 — 2026년 42주차

> 기간: 2026-10-12 ~ 2026-10-18 · 생성: 2026-10-15 04:34 KST · 계산 범위: 최근 30일 · 자동 생성 (GitHub Actions)

![DORA dashboard](../metrics/dora-dashboard.png)

## 1. 핵심 지표

| 지표 | 값 | 성과 등급 | 지난 측정 대비 |
|---|---|---|---|
| 🚀 배포 빈도 (Deployment Frequency) | **28.0회 / 주** | 🟢 Elite | ▲ 7.0회 (개선) |
| ⏱️ 변경 리드타임 (Lead Time for Changes) | **2 min** (중앙값) | 🟢 Elite | ▲ 0.0h (악화) |
| 💥 변경 실패율 (Change Failure Rate) | **20.0%** | 🟡 Medium | ▼ 5.0%p (개선) |
| 🛠️ 평균 복구 시간 (MTTR) | **1 min** | 🟢 Elite | 변화 없음 |

- 전체 배포 **5회** (성공 4 · 실패 1), 복구 1회

## 2. 이번 주 배포 기록

| # | 완료 시각 (KST) | 결과 | 커밋 | 리드타임 |
|---|---|---|---|---|
| [5](https://github.com/hwsseo/ossproject/actions/runs/38624705638) | 10-15 04:33 | ✅ 성공 | `04f418b` docs: add week2 screenshots | 10 min |
| [4](https://github.com/hwsseo/ossproject/actions/runs/38623259462) | 10-15 04:23 | ✅ 성공 | `6980b65` Deploy | 1 min |
| [3](https://github.com/hwsseo/ossproject/actions/runs/38623200111) | 10-15 04:23 | ❌ 실패 | `3e7f2d1` Deploy | — |
| [2](https://github.com/hwsseo/ossproject/actions/runs/38623139532) | 10-15 04:22 | ✅ 성공 | `3e7f2d1` Deploy | 4 min |
| [1](https://github.com/hwsseo/ossproject/actions/runs/38622584590) | 10-15 04:18 | ✅ 성공 | `b206c8d` ci: add deploy and DORA metrics workflows | 1 min |

## 3. 해석 및 다음 주 액션

- 실패율이 15%를 넘습니다 → 배포 전 테스트(CI) 강화하기 (7·12주차 과제와 연계)

---
<sub>이 보고서는 `scripts/dora_metrics.py`가 Deploy 워크플로우 기록을 분석해 자동으로 생성했습니다.</sub>
