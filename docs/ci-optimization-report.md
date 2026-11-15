# 📈 [8주차] CI 워크플로우 최적화 전후 비교 리포트

> 비교 대상: **최적화 전** [`ci-basic.yml`](../.github/workflows/ci-basic.yml) (7주차) ↔ **최적화 후** [`ci-optimized.yml`](../.github/workflows/ci-optimized.yml) (8주차)
> 캐싱 실측값: [`reports/ci-cache-benchmark.md`](../reports/ci-cache-benchmark.md) (Actions가 자동 측정·커밋)

## 1. 한눈에 비교

| 항목 | 최적화 전 (7주차) | 최적화 후 (8주차) |
|---|---|---|
| 테스트 Matrix | 2 OS × 3 Python = **6개** | 3 OS × 3 Python − exclude 1 + include 1 = **9개** |
| 중복 코드 | 각 job마다 setup-python·pip install 반복 | **Composite Action** `setup-maeumi` 1곳에서 관리 |
| 테스트 절차 | job 안에 직접 작성 | **Reusable Workflow** `reusable-python-test.yml` 호출 |
| 의존성 캐시 | 없음 | **pip 캐시** (`setup-python` cache + `actions/cache`) |
| 문서만 바꿨을 때 | Lint·Test·Build·Deploy 전부 실행 | **변경 파일 감지**로 코드 job 전부 skip |
| 배포 조건 | main push면 항상 | main push **+ 서버 코드 변경 시에만** |
| 중복 실행 | 같은 브랜치 연속 push 시 모두 실행 | `concurrency` + `cancel-in-progress`로 이전 실행 취소 |
| 테스트 결과 | 로그로만 확인 | JUnit XML **아티팩트**로 보관 |

## 2. 재사용 구조

```
ci-optimized.yml
 ├─ changes  (dorny/paths-filter) ──┐ code 변경?
 ├─ lint     ── uses: ./.github/actions/setup-maeumi      (Composite)
 ├─ test     ── uses: ./.github/workflows/reusable-python-test.yml  × 9 (Matrix)
 │                └─ uses: ./.github/actions/setup-maeumi (Composite)
 ├─ build    ── 아티팩트 업로드
 └─ deploy   ── if: main push && code 변경  → 아티팩트 다운로드 후 배포
```

- Python 버전·캐시 설정을 바꿀 때 **Composite Action 한 파일만 수정**하면 lint/test/build 전체에 반영된다.
- 새 OS/버전 조합 추가는 Matrix에 한 줄 추가로 끝난다.

## 3. 캐싱 효과 (실측)

`cache-benchmark.yml`이 같은 러너에서 **캐시 없이 설치** vs **pip 캐시로 설치** 시간을 측정해 `reports/ci-cache-benchmark.md`에 기록한다.
→ 최신 수치는 [ci-cache-benchmark.md](../reports/ci-cache-benchmark.md) 참고.

## 4. 조건부 실행 효과

| 변경 내용 | 최적화 전 실행 job | 최적화 후 실행 job |
|---|---|---|
| `README.md`만 수정 | lint 1 + test 6 + build 1 + deploy 1 = **9개** | changes 1 = **1개** (나머지 skip) |
| `server/` 코드 수정 (main) | 9개 | changes 1 + lint 1 + test 9 + build 1 + deploy 1 = 13개 (더 넓은 범위 검증) |
| PR (코드 수정) | 8개 (deploy만 skip) | 12개, deploy 없음 |

→ 문서 수정이 잦은 이 프로젝트(주간 보고서·지표 자동 커밋)에서 **불필요한 CI 실행을 약 89% 줄인다** (9 → 1 job).
