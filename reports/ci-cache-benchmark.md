# ⚡ CI 캐싱 전후 비교 리포트 (자동 생성)

> 측정: 2026-11-15 17:40 KST · [실행 기록](https://github.com/hwsseo/ossproject/actions/runs/43695549592) · Runner: ubuntu-latest / Python 3.12

| 구분 | 의존성 설치 시간 |
|---|---|
| ① 최적화 전 (캐시 없음, `--no-cache-dir`) | **5.54초** |
| ② 최적화 후 (pip 캐시 사용) | **4.92초** |
| **개선률** | **11.2% 단축** (0.62초 절약) |

- actions/cache 상태: 미스(miss) → 이번 실행에서 저장
- 대상 패키지: `requirements-dev.txt` (pytest, ruff, fastapi, uvicorn, httpx)
- CI Optimized의 테스트 Matrix는 9개 job이 같은 설치를 반복하므로, job당 절약 시간 × 9만큼 전체 실행 시간이 줄어든다.
