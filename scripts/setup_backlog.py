"""
백로그 자동 구성 스크립트 (3주차)
================================
GitHub 저장소에 아래를 한 번에 만든다. 여러 번 실행해도 중복으로 만들지 않는다.

  1) 라벨 체계   : type / priority / area / points
  2) 마일스톤 2개: M1(11/15), M2(12/13)
  3) 이슈 17개   : 제안서의 핵심 기능 3개 + 주차별 과제를 쪼갠 작업
                   이미 끝난 작업(1·2주차)은 Closed 처리

실행: GitHub Actions의 "Setup Backlog" 워크플로우 (REPO, GITHUB_TOKEN 필요)
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

REPO = os.environ.get("REPO", "")
TOKEN = os.environ.get("GITHUB_TOKEN", "")

# ── 1) 라벨 ─────────────────────────────────────────────────
LABELS = [
    # 종류
    ("type: feature", "1f883d", "새 기능"),
    ("type: bug", "d73a4a", "잘못 동작하는 부분"),
    ("type: docs", "0075ca", "문서 작업"),
    ("type: chore", "8c959f", "환경 설정·관리 작업"),
    ("type: ci", "6f42c1", "CI/CD·자동화"),
    ("type: test", "bf8700", "테스트"),
    ("type: security", "b60205", "보안"),
    # 우선순위
    ("priority: high", "d93f0b", "가장 먼저"),
    ("priority: medium", "fbca04", "보통"),
    ("priority: low", "c2e0c6", "여유 있을 때"),
    # 영역
    ("area: app", "bfdadc", "Flutter 앱"),
    ("area: server", "c5def5", "FastAPI 서버"),
    ("area: ai", "f9d0c4", "Gemini AI 연동"),
    ("area: devops", "d4c5f9", "GitHub·Actions·배포"),
    # 작업량 (Story Point → Velocity·Burndown 계산에 사용)
    ("points: 1", "ededed", "반나절"),
    ("points: 2", "ededed", "하루"),
    ("points: 3", "ededed", "2~3일"),
    ("points: 5", "ededed", "일주일"),
    ("points: 8", "ededed", "일주일 이상 (쪼개기 권장)"),
]

# ── 2) 마일스톤 ─────────────────────────────────────────────
MILESTONES = [
    ("M1 · 기반 구축 + AI 대화", "2026-11-15T14:59:59Z",
     "1~8주차: 개발 환경·DORA·백로그·협업 체계 구축, 기능 1(AI 마음 대화) 완성, CI/CD 구축"),
    ("M2 · 감정 기록 + 위기 감지 + 배포", "2026-12-13T14:59:59Z",
     "9~16주차: 기능 2(감정 기록·주간 리포트), 기능 3(위기 신호 감지), 보안·멀티 플랫폼 배포·실험"),
]
M1, M2 = MILESTONES[0][0], MILESTONES[1][0]

# ── 3) 이슈 ─────────────────────────────────────────────────
# (제목, 라벨, 마일스톤, 이미 완료?, 본문, 보드 컬럼 안내)
ISSUES = [
    ("[Chore] Git/GitHub 개발 환경 구축 (SSH 키·저장소·첫 커밋)",
     ["type: chore", "area: devops", "priority: high", "points: 2"], M1, True, "Done",
     "- [x] Git 설치 및 사용자 정보 등록\n- [x] SSH 키 생성·GitHub 등록·연결 테스트\n- [x] 저장소 생성 및 첫 커밋/푸시"),
    ("[Docs] 프로젝트 제안서 작성 (문제정의·핵심 기능·기술 스택·마일스톤)",
     ["type: docs", "priority: high", "points: 3"], M1, True, "Done",
     "- [x] 문제 정의 3가지\n- [x] 핵심 기능 3개\n- [x] 기술 스택\n- [x] 16주 마일스톤\n\n📄 `PROPOSAL.md`"),
    ("[CI] DORA 4대 지표 자동 수집 파이프라인",
     ["type: ci", "area: devops", "priority: high", "points: 5"], M1, True, "Done",
     "- [x] Deploy 워크플로우 (production 배포 기록)\n- [x] DORA Metrics 워크플로우 (Lead Time·배포 빈도·MTTR·실패율)\n"
     "- [x] 대시보드 이미지 README 자동 첨부\n- [x] JSON 아티팩트 + 주간 보고서"),
    ("[Chore] GitHub Projects 칸반·이슈 템플릿·라벨·마일스톤 구성",
     ["type: chore", "area: devops", "priority: high", "points: 3"], M1, False, "In Progress",
     "- [ ] 칸반 보드 (Backlog / To Do / In Progress / Review / Done)\n- [x] 이슈 템플릿 (Bug / Feature)\n"
     "- [x] 라벨 체계 (type / priority / area / points)\n- [x] 마일스톤 2개\n- [ ] Cycle Time·Velocity·Burndown 분석"),
    ("[Bug] README 대시보드 이미지가 갱신 후에도 이전 이미지로 표시됨",
     ["type: bug", "area: devops", "priority: low", "points: 1"], M1, False, "To Do",
     "**어떤 문제?** DORA Metrics가 새 대시보드를 커밋했는데 README에는 몇 분간 예전 이미지가 보임\n\n"
     "**원인 추정** GitHub 이미지 캐시 (파일 이름이 같아서)\n\n"
     "**해결 방안** README 이미지 주소 뒤에 갱신 시각 쿼리(`?v=...`)를 붙여 캐시 무효화"),
    ("[Chore] Flutter 앱 · FastAPI 서버 프로젝트 골격 생성",
     ["type: chore", "area: app", "area: server", "priority: high", "points: 3"], M1, False, "To Do",
     "- [ ] `app/` Flutter 프로젝트 생성\n- [ ] `server/` FastAPI 프로젝트 생성 (`/health` 엔드포인트)\n- [ ] 실행 방법 README 정리"),
    ("[Docs] GitHub Flow 브랜치 전략 · PR 템플릿 · 코드리뷰 규칙",
     ["type: docs", "area: devops", "priority: medium", "points: 2"], M1, False, "To Do",
     "- [ ] `main` 보호 규칙\n- [ ] `feature/이슈번호-설명` 브랜치 규칙\n- [ ] PR 템플릿·리뷰 체크리스트"),
    ("[Docs] ADR(아키텍처 결정 기록) · Wiki API 명세",
     ["type: docs", "priority: medium", "points: 2"], M1, False, "Backlog",
     "- [ ] ADR-001: 무료 Gemini API 선택 이유\n- [ ] ADR-002: 앱-서버 분리 구조\n- [ ] Wiki에 API 명세 정리"),
    ("[Feature] AI 마음 대화 API (Gemini 연동 + Fallback)",
     ["type: feature", "area: server", "area: ai", "priority: high", "points: 5"], M1, False, "Backlog",
     "**완료 조건**\n- [ ] `POST /chat` → Gemini Flash 응답 반환\n- [ ] API 키는 서버 환경변수로만 관리\n"
     "- [ ] 호출 실패·한도 초과(429) 시 기본 응답 반환\n- [ ] 대화 톤(공감형/정리형) 프롬프트 분리"),
    ("[Feature] 채팅 화면 UI + 서버 연동",
     ["type: feature", "area: app", "priority: high", "points: 5"], M1, False, "Backlog",
     "**완료 조건**\n- [ ] 말풍선 목록 + 입력창 + 전송 버튼\n- [ ] `/chat` 호출 후 답장 표시\n- [ ] 응답 대기 중 로딩 표시"),
    ("[CI] 테스트·빌드 CI 구축 + GitHub Secrets로 API 키 관리",
     ["type: ci", "area: devops", "priority: medium", "points: 3"], M1, False, "Backlog",
     "- [ ] PR마다 pytest · flutter test 자동 실행\n- [ ] Gemini API 키를 Secrets로 관리\n- [ ] 캐싱으로 실행 시간 단축"),
    ("[Feature] 감정 기록 DB · API",
     ["type: feature", "area: server", "priority: medium", "points: 3"], M2, False, "Backlog",
     "- [ ] SQLite 감정 기록 테이블\n- [ ] 대화 종료 시 감정·강도 저장\n- [ ] 내 기록 내보내기·삭제 API"),
    ("[Feature] 주간 마음 리포트 화면",
     ["type: feature", "area: app", "priority: medium", "points: 5"], M2, False, "Backlog",
     "- [ ] 최근 7일 감정 분포 그래프\n- [ ] 많이 언급한 고민 키워드\n- [ ] 기록이 없을 때 안내 문구"),
    ("[Feature] 위기 신호 감지 & 도움 기관 안내",
     ["type: feature", "area: server", "area: app", "priority: high", "points: 5"], M2, False, "Backlog",
     "- [ ] 위험 표현 감지 시 일반 응답 대신 안내 화면 우선 표시\n- [ ] 109 · 1577-0199 · 학생상담센터 전화 연결 버튼\n"
     "- [ ] 애매하면 안내하는 쪽으로 설계"),
    ("[Test] 위기 감지 테스트 케이스 자동화",
     ["type: test", "area: server", "priority: high", "points: 3"], M2, False, "Backlog",
     "- [ ] 감지해야 하는 문장 / 감지하면 안 되는 문장 케이스 목록\n- [ ] pytest로 CI에서 자동 실행\n- [ ] 통과율 95% 이상"),
    ("[Feature] 대화 톤 선택을 Feature Flag로 점진적 공개",
     ["type: feature", "area: app", "area: server", "priority: low", "points: 3"], M2, False, "Backlog",
     "- [ ] '정리형' 톤을 플래그로 켜고 끄기\n- [ ] 일부 사용자에게만 먼저 공개\n- [ ] 13주차 A/B 실험과 연계"),
    ("[Security] Dependabot · CodeQL 의존성 보안 점검",
     ["type: security", "area: devops", "priority: medium", "points: 2"], M2, False, "Backlog",
     "- [ ] Dependabot 설정 (pip · pub)\n- [ ] CodeQL 코드 스캔\n- [ ] 발견된 취약점 처리 기록"),
]


# ── GitHub API ──────────────────────────────────────────────
def api(method: str, path: str, body: dict | None = None):
    url = f"https://api.github.com{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {path} → {e.code}: {e.read().decode()[:300]}") from e


def get_all(path: str) -> list:
    out, page = [], 1
    sep = "&" if "?" in path else "?"
    while True:
        batch = api("GET", f"{path}{sep}per_page=100&page={page}")
        out += batch
        if len(batch) < 100:
            return out
        page += 1


def main() -> None:
    # 1) 라벨: 없으면 만들고, 있으면 색·설명 맞추기
    existing = {lb["name"]: lb for lb in get_all(f"/repos/{REPO}/labels")}
    for name, color, desc in LABELS:
        if name in existing:
            api("PATCH", f"/repos/{REPO}/labels/{urllib.parse.quote(name)}",
                {"color": color, "description": desc})
            print(f"🏷️  라벨 갱신: {name}")
        else:
            api("POST", f"/repos/{REPO}/labels", {"name": name, "color": color, "description": desc})
            print(f"🏷️  라벨 생성: {name}")

    # 2) 마일스톤
    ms = {m["title"]: m for m in get_all(f"/repos/{REPO}/milestones?state=all")}
    for title, due, desc in MILESTONES:
        if title not in ms:
            ms[title] = api("POST", f"/repos/{REPO}/milestones",
                            {"title": title, "due_on": due, "description": desc})
            print(f"🎯 마일스톤 생성: {title}")
        else:
            print(f"🎯 마일스톤 있음: {title}")

    # 3) 이슈
    issues = {i["title"]: i for i in get_all(f"/repos/{REPO}/issues?state=all")
              if "pull_request" not in i}
    board = []
    for title, labels, milestone, done, column, body in ISSUES:
        full_body = body + f"\n\n---\n<sub>📋 칸반 보드 컬럼: **{column}**</sub>"
        if title in issues:
            issue = issues[title]
            print(f"📌 이슈 있음: #{issue['number']} {title}")
        else:
            issue = api("POST", f"/repos/{REPO}/issues", {
                "title": title, "body": full_body, "labels": labels,
                "milestone": ms[milestone]["number"],
            })
            print(f"📌 이슈 생성: #{issue['number']} {title}")
        if done and issue["state"] == "open":
            api("PATCH", f"/repos/{REPO}/issues/{issue['number']}",
                {"state": "closed", "state_reason": "completed"})
            print(f"   ✅ 완료 처리: #{issue['number']}")
        board.append((column, issue["number"], title))

    # 보드 배치 안내 (Actions 로그에 표로 출력)
    print("\n================ 칸반 보드 배치 안내 ================")
    for col in ["Backlog", "To Do", "In Progress", "Review", "Done"]:
        items = [f"#{n} {t}" for c, n, t in board if c == col]
        print(f"\n[{col}] {len(items)}개")
        for it in items:
            print(f"  - {it}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write("## 📋 칸반 보드 배치 안내\n\n| 컬럼 | 이슈 |\n|---|---|\n")
            for c, n, t in board:
                f.write(f"| {c} | #{n} {t} |\n")
    print("\n✅ 완료")


if __name__ == "__main__":
    main()
