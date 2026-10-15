"""
애자일 지표 자동 분석 스크립트 (3주차 선택과제)
==============================================
이슈 기록을 읽어서 3가지 지표를 계산하고 파일로 남긴다.

  1) Cycle Time  : 이슈 하나가 끝나기까지 걸린 시간 (생성 → 완료)
  2) Velocity    : 스프린트(2주)마다 끝낸 Story Point 합계
  3) Burndown    : 마일스톤별 남은 Story Point 가 마감일까지 줄어드는 모습 (이상선과 비교)

Story Point 는 이슈의 `points: N` 라벨에서 읽는다 (없으면 1점).

만들어지는 파일
  metrics/agile-latest.json    이번 계산 결과
  metrics/agile-dashboard.png  대시보드 이미지 (README에 첨부)
  reports/agile-YYYY-Www.md    주간 애자일 보고서
  README.md                    <!-- AGILE:START --> ~ <!-- AGILE:END --> 구간 자동 갱신

실행
  GitHub Actions 안에서:  python scripts/agile_metrics.py   (REPO, GITHUB_TOKEN 필요)
  내 컴퓨터에서 연습용:    python scripts/agile_metrics.py --mock
"""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, median

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

# ── 설정 ────────────────────────────────────────────────────
SPRINT_START = date(2026, 10, 12)   # 스프린트 1 시작일 (월요일)
SPRINT_DAYS = 14                    # 스프린트 길이 (2주)
KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
METRICS_DIR = ROOT / "metrics"
REPORTS_DIR = ROOT / "reports"
README = ROOT / "README.md"

C = {
    "surface": "#fcfcfb", "ink": "#0b0b0b", "ink2": "#52514e", "muted": "#898781",
    "grid": "#e1e0d9", "axis": "#c3c2b7", "blue": "#2a78d6", "ideal": "#b5b3aa",
    "tile": "#f4f3ef",
}


# ── 데이터 수집 ─────────────────────────────────────────────
def gh(path: str):
    req = urllib.request.Request(f"https://api.github.com{path}", headers={
        "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def ts(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def points_of(labels: list[str]) -> int:
    for name in labels:
        m = re.fullmatch(r"points:\s*(\d+)", name.strip())
        if m:
            return int(m.group(1))
    return 1


def fetch(repo: str) -> tuple[list[dict], list[dict]]:
    issues, page = [], 1
    while True:
        batch = gh(f"/repos/{repo}/issues?state=all&per_page=100&page={page}")
        for i in batch:
            if "pull_request" in i:
                continue
            if i.get("state_reason") == "not_planned":
                continue  # "계획 없음"으로 닫은 이슈는 제외
            labels = [lb["name"] for lb in i["labels"]]
            issues.append({
                "number": i["number"], "title": i["title"], "url": i["html_url"],
                "created": ts(i["created_at"]), "closed": ts(i["closed_at"]),
                "points": points_of(labels), "labels": labels,
                "milestone": i["milestone"]["title"] if i.get("milestone") else None,
            })
        if len(batch) < 100:
            break
        page += 1
    milestones = [{
        "title": m["title"], "due": ts(m["due_on"]), "created": ts(m["created_at"]),
    } for m in gh(f"/repos/{repo}/milestones?state=all&per_page=100")]
    return issues, milestones


def mock(now: datetime) -> tuple[list[dict], list[dict]]:
    import random
    random.seed(3)
    m1 = {"title": "M1 · 기반 구축 + AI 대화", "due": datetime(2026, 11, 15, 14, 59, tzinfo=timezone.utc),
          "created": now - timedelta(days=20)}
    m2 = {"title": "M2 · 감정 기록 + 위기 감지 + 배포", "due": datetime(2026, 12, 13, 14, 59, tzinfo=timezone.utc),
          "created": now - timedelta(days=20)}
    issues = []
    for n in range(1, 18):
        created = now - timedelta(days=random.uniform(12, 20))
        closed = created + timedelta(days=random.uniform(0.5, 9)) if n <= 9 else None
        if closed and closed > now:
            closed = None
        issues.append({"number": n, "title": f"mock issue {n}", "url": "#", "created": created,
                       "closed": closed, "points": random.choice([1, 2, 3, 5]), "labels": [],
                       "milestone": m1["title"] if n <= 11 else m2["title"]})
    return issues, [m1, m2]


# ── 계산 ────────────────────────────────────────────────────
def sprint_of(d: date) -> int:
    return (d - SPRINT_START).days // SPRINT_DAYS + 1


def sprint_range(n: int) -> tuple[date, date]:
    s = SPRINT_START + timedelta(days=(n - 1) * SPRINT_DAYS)
    return s, s + timedelta(days=SPRINT_DAYS - 1)


def hours(td: timedelta) -> float:
    return td.total_seconds() / 3600


def compute(issues: list[dict], milestones: list[dict], now: datetime) -> dict:
    today = now.astimezone(KST).date()
    closed = [i for i in issues if i["closed"]]

    # 1) Cycle Time
    for i in issues:
        i["cycle_hours"] = round(hours(i["closed"] - i["created"]), 2) if i["closed"] else None
    cts = [i["cycle_hours"] for i in closed]

    # 2) Velocity (스프린트별 완료 포인트)
    cur = max(1, sprint_of(today))
    velocity = []
    for n in range(1, cur + 1):
        s, e = sprint_range(n)
        lo = date.min if n == 1 else s  # 스프린트 1 이전에 끝난 이슈는 스프린트 1에 포함
        done = [i for i in closed if lo <= i["closed"].astimezone(KST).date() <= e]
        velocity.append({"sprint": n, "start": s.isoformat(), "end": e.isoformat(),
                         "points": sum(i["points"] for i in done), "issues": len(done),
                         "in_progress": n == cur})
    finished = [v["points"] for v in velocity if not v["in_progress"]]
    avg_velocity = round(mean(finished), 1) if finished else None

    # 3) Burndown (마일스톤별)
    burndowns = []
    for m in milestones:
        mi = [i for i in issues if i["milestone"] == m["title"]]
        if not mi or not m["due"]:
            continue
        start = min([m["created"]] + [i["created"] for i in mi]).astimezone(KST).date()
        due = m["due"].astimezone(KST).date()
        total = sum(i["points"] for i in mi)
        days = [start + timedelta(days=k) for k in range((due - start).days + 1)]
        actual = []
        for d in days:
            if d > today:
                break
            scope = sum(i["points"] for i in mi if i["created"].astimezone(KST).date() <= d)
            burned = sum(i["points"] for i in mi if i["closed"] and i["closed"].astimezone(KST).date() <= d)
            actual.append({"date": d.isoformat(), "remaining": scope - burned})
        span = max(1, (due - start).days)
        ideal = [{"date": d.isoformat(), "remaining": round(total * (1 - k / span), 2)} for k, d in enumerate(days)]
        done_pts = sum(i["points"] for i in mi if i["closed"])
        remaining_now = actual[-1]["remaining"] if actual else total
        ideal_now = next((x["remaining"] for x in ideal if x["date"] == today.isoformat()), None)
        burndowns.append({
            "milestone": m["title"], "start": start.isoformat(), "due": due.isoformat(),
            "total_points": total, "done_points": done_pts,
            "progress_pct": round(done_pts / total * 100, 1) if total else 0.0,
            "remaining_points": remaining_now, "ideal_remaining_today": ideal_now,
            "days_left": (due - today).days, "actual": actual, "ideal": ideal,
        })

    return {
        "cycle_time_hours_median": round(median(cts), 2) if cts else None,
        "cycle_time_hours_mean": round(mean(cts), 2) if cts else None,
        "current_sprint": cur,
        "current_sprint_points": velocity[-1]["points"] if velocity else 0,
        "avg_velocity": avg_velocity,
        "velocity": velocity,
        "burndowns": burndowns,
        "counts": {"issues": len(issues), "closed": len(closed), "open": len(issues) - len(closed),
                   "points_total": sum(i["points"] for i in issues),
                   "points_done": sum(i["points"] for i in closed)},
    }


def fmt_h(h) -> str:
    if h is None:
        return "N/A"
    if h < 1:
        return f"{h * 60:.0f} min"
    if h < 48:
        return f"{h:.1f} h"
    return f"{h / 24:.1f} d"


# ── 대시보드 ────────────────────────────────────────────────
def draw(m: dict, now: datetime, path: Path) -> None:
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.edgecolor": C["axis"], "xtick.color": C["muted"], "ytick.color": C["muted"]})
    fig = plt.figure(figsize=(12, 6.8), dpi=150, facecolor=C["surface"])
    fig.text(0.04, 0.945, "Agile Metrics Dashboard", fontsize=17, fontweight="bold", color=C["ink"])
    c = m["counts"]
    fig.text(0.04, 0.905, f"Sprint {m['current_sprint']} (2-week sprints)  ·  updated "
             f"{now.astimezone(KST):%Y-%m-%d %H:%M} KST  ·  {c['closed']}/{c['issues']} issues done  ·  "
             f"{c['points_done']}/{c['points_total']} pts", fontsize=9.5, color=C["ink2"])

    bd = {b["milestone"][:2]: b for b in m["burndowns"]}
    tiles = [
        ("Cycle time", fmt_h(m["cycle_time_hours_median"]), "median"),
        ("Velocity", f"{m['current_sprint_points']} pts", f"sprint {m['current_sprint']}\n(so far)"),
        ("M1 progress", f"{bd['M1']['progress_pct']:.0f}%" if "M1" in bd else "N/A",
         f"{bd['M1']['days_left']} days left" if "M1" in bd else ""),
        ("M2 progress", f"{bd['M2']['progress_pct']:.0f}%" if "M2" in bd else "N/A",
         f"{bd['M2']['days_left']} days left" if "M2" in bd else ""),
    ]
    x0, w, gap, y0, h = 0.04, 0.215, 0.0133, 0.66, 0.2
    for k, (label, value, sub) in enumerate(tiles):
        x = x0 + k * (w + gap)
        fig.patches.append(FancyBboxPatch((x, y0), w, h, boxstyle="round,pad=0,rounding_size=0.012",
                                          transform=fig.transFigure, facecolor=C["tile"], edgecolor="none"))
        fig.text(x + 0.015, y0 + h - 0.045, label, fontsize=10, color=C["ink2"])
        fig.text(x + 0.015, y0 + 0.05, value, fontsize=26, fontweight="bold", color=C["ink"])
        fig.text(x + w - 0.015, y0 + 0.058, sub, fontsize=9, color=C["muted"], ha="right", linespacing=1.5)

    # ① Burndown (M1)
    ax1 = fig.add_axes([0.06, 0.1, 0.42, 0.44])
    b = bd.get("M1") or (m["burndowns"][0] if m["burndowns"] else None)
    if b:
        idx = {d["date"]: k for k, d in enumerate(b["ideal"])}
        ax1.plot([idx[d["date"]] for d in b["ideal"]], [d["remaining"] for d in b["ideal"]],
                 color=C["ideal"], linewidth=1.5, label="Ideal", zorder=2)
        ax_x = [idx[d["date"]] for d in b["actual"] if d["date"] in idx]
        ax_y = [d["remaining"] for d in b["actual"] if d["date"] in idx]
        ax1.plot(ax_x, ax_y, color=C["blue"], linewidth=2, label="Remaining", zorder=3,
                 solid_joinstyle="round", solid_capstyle="round")
        if ax_x:
            ax1.scatter([ax_x[-1]], [ax_y[-1]], s=40, color=C["blue"], edgecolors=C["surface"],
                        linewidths=2, zorder=4)
            ax1.annotate(f"{ax_y[-1]} pts left", (ax_x[-1], ax_y[-1]), xytext=(8, 6),
                         textcoords="offset points", fontsize=8.5, color=C["ink2"])
        n = len(b["ideal"])
        step = max(1, n // 6)
        ticks = list(range(0, n, step))
        if ticks[-1] != n - 1:
            if n - 1 - ticks[-1] < step * 0.6:
                ticks[-1] = n - 1  # 마지막 눈금이 마감일과 겹치지 않게
            else:
                ticks.append(n - 1)
        ax1.set_xticks(ticks, [b["ideal"][t]["date"][5:].replace("-", "/") for t in ticks])
        ax1.set_ylim(0, b["total_points"] * 1.12 + 1)
        ax1.set_xlim(-0.5, n - 0.5)
        ax1.legend(loc="upper right", frameon=False, fontsize=9, labelcolor=C["ink2"])
        ax1.set_title(f"Burndown · M1 (due {b['due'][5:].replace('-', '/')}, story points)",
                      loc="left", fontsize=11, color=C["ink"], pad=10)
    else:
        ax1.text(0.5, 0.5, "No milestone data", ha="center", va="center", transform=ax1.transAxes,
                 color=C["muted"])

    # ② Velocity
    ax2 = fig.add_axes([0.56, 0.1, 0.40, 0.44])
    vs = m["velocity"]
    xs = list(range(len(vs)))
    bars = ax2.bar(xs, [v["points"] for v in vs], width=0.55, color=C["blue"], zorder=3)
    for bar, v in zip(bars, vs):
        if v["in_progress"]:
            bar.set_alpha(0.45)
        ax2.annotate(f"{v['points']}", (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                     xytext=(0, 4), textcoords="offset points", ha="center", fontsize=9, color=C["ink2"])
    ax2.set_xticks(xs, [f"S{v['sprint']}" + ("\n(now)" if v["in_progress"] else "") for v in vs])
    ax2.set_xlim(-0.8, max(3, len(vs)) - 0.2)
    ax2.set_ylim(0, max(5, max((v["points"] for v in vs), default=0) * 1.3))
    if m["avg_velocity"] is not None:
        ax2.axhline(m["avg_velocity"], color=C["muted"], linewidth=1, zorder=2)
        ax2.text(0.01, m["avg_velocity"], f"avg {m['avg_velocity']} pts", transform=ax2.get_yaxis_transform(),
                 va="bottom", fontsize=8.5, color=C["ink2"])
    ax2.set_title("Velocity per sprint (story points done)", loc="left", fontsize=11, color=C["ink"], pad=10)

    for ax in (ax1, ax2):
        ax.set_facecolor(C["surface"])
        ax.grid(axis="y", color=C["grid"], linewidth=0.8, zorder=0)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.tick_params(length=0)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=C["surface"])
    plt.close(fig)


# ── 보고서 / README ─────────────────────────────────────────
def burndown_status(b: dict) -> str:
    if b["ideal_remaining_today"] is None:
        return "—"
    diff = b["remaining_points"] - b["ideal_remaining_today"]
    if diff <= 0:
        return f"🟢 계획보다 {abs(diff):.0f}pt 앞섬"
    if diff <= 3:
        return f"🟡 계획보다 {diff:.0f}pt 뒤처짐"
    return f"🔴 계획보다 {diff:.0f}pt 뒤처짐"


def summary_rows(m: dict) -> list[str]:
    avg = "" if m["avg_velocity"] is None else f" · 평균 {m['avg_velocity']}pt"
    rows = ["| 지표 | 값 | 설명 |", "|---|---|---|",
            f"| ⏱️ Cycle Time | **{fmt_h(m['cycle_time_hours_median'])}** (중앙값) "
            f"· 평균 {fmt_h(m['cycle_time_hours_mean'])} | 이슈 생성 → 완료까지 걸린 시간 |",
            f"| 🏃 Velocity | **스프린트 {m['current_sprint']}: {m['current_sprint_points']}pt** (진행 중){avg} "
            f"| 2주 스프린트마다 끝낸 Story Point |"]
    for b in m["burndowns"]:
        rows.append(f"| 🔥 Burndown · {b['milestone']} | **{b['progress_pct']:.0f}%** 완료 "
                    f"({b['done_points']}/{b['total_points']}pt, D-{b['days_left']}) | {burndown_status(b)} |")
    return rows


def write_report(m: dict, issues: list[dict], now: datetime) -> Path:
    kst = now.astimezone(KST)
    y, wk, _ = kst.isocalendar()
    path = REPORTS_DIR / f"agile-{y}-W{wk:02d}.md"
    s, e = sprint_range(m["current_sprint"])
    lines = [
        f"# 🏃 애자일 주간 보고서 — {y}년 {wk}주차",
        "",
        f"> 스프린트 {m['current_sprint']} ({s} ~ {e}) · 생성: {kst:%Y-%m-%d %H:%M} KST · 자동 생성 (GitHub Actions)",
        "",
        "![Agile dashboard](../metrics/agile-dashboard.png)",
        "",
        "## 1. 핵심 지표",
        "",
        *summary_rows(m),
        "",
        "## 2. 스프린트별 Velocity",
        "",
        "| 스프린트 | 기간 | 완료 이슈 | 완료 포인트 |",
        "|---|---|---|---|",
        *[f"| S{v['sprint']}{' (진행 중)' if v['in_progress'] else ''} | {v['start']} ~ {v['end']} "
          f"| {v['issues']} | {v['points']}pt |" for v in m["velocity"]],
        "",
        "## 3. 완료된 이슈 (Cycle Time)",
        "",
    ]
    done = sorted([i for i in issues if i["closed"]], key=lambda i: i["closed"], reverse=True)
    if done:
        lines += ["| 이슈 | 포인트 | 완료일 | Cycle Time |", "|---|---|---|---|"]
        lines += [f"| [#{i['number']}]({i['url']}) {i['title']} | {i['points']} "
                  f"| {i['closed'].astimezone(KST):%m-%d} | {fmt_h(i['cycle_hours'])} |" for i in done]
    else:
        lines.append("아직 완료된 이슈가 없습니다.")

    lines += ["", "## 4. 해석 및 다음 스프린트 액션", ""]
    tips = []
    for b in m["burndowns"]:
        if b["ideal_remaining_today"] is not None and b["remaining_points"] > b["ideal_remaining_today"] + 3:
            tips.append(f"{b['milestone'][:2]}이 계획보다 늦습니다 → 우선순위 high 이슈부터 처리하고, 큰 이슈(5pt 이상)는 쪼개기")
    if m["cycle_time_hours_median"] and m["cycle_time_hours_median"] > 24 * 7:
        tips.append("Cycle Time이 일주일을 넘습니다 → 이슈를 더 작은 단위로 나누기")
    if not tips:
        tips.append("계획대로 진행 중입니다 → In Progress 카드를 2개 이하로 유지하며 흐름 지키기")
    lines += [f"- {t}" for t in tips]
    lines += ["", "---", "<sub>`scripts/agile_metrics.py`가 이슈 기록을 분석해 자동으로 생성했습니다. "
              "Cycle Time은 이슈 생성 시각부터 완료(Closed) 시각까지로 계산합니다.</sub>", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def update_readme(m: dict, report: Path, now: datetime) -> None:
    v = int(now.timestamp())
    block = "\n".join([
        "<!-- AGILE:START -->",
        "## 🏃 애자일 지표 (자동 갱신)",
        "",
        f"> 최근 갱신: {now.astimezone(KST):%Y-%m-%d %H:%M} KST · "
        f"[최신 애자일 보고서]({report.relative_to(ROOT).as_posix()}) · [원본 JSON](metrics/agile-latest.json)",
        "",
        f"![Agile dashboard](metrics/agile-dashboard.png?v={v})",
        "",
        *summary_rows(m),
        "<!-- AGILE:END -->",
    ])
    text = README.read_text(encoding="utf-8") if README.exists() else "# ossproject\n"
    if "<!-- AGILE:START -->" in text:
        text = re.sub(r"<!-- AGILE:START -->.*?<!-- AGILE:END -->", lambda _: block, text, flags=re.S)
    else:
        text = text.rstrip() + "\n\n" + block + "\n"
    README.write_text(text, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true")
    args = ap.parse_args()
    now = datetime.now(timezone.utc)
    issues, milestones = mock(now) if args.mock else fetch(os.environ["REPO"])
    print(f"이슈 {len(issues)}개 · 마일스톤 {len(milestones)}개")

    m = compute(issues, milestones, now)
    METRICS_DIR.mkdir(exist_ok=True)
    draw(m, now, METRICS_DIR / "agile-dashboard.png")
    report = write_report(m, issues, now)
    update_readme(m, report, now)

    out = {"generated_at": now.isoformat(timespec="seconds"), **m,
           "issues": [{"number": i["number"], "title": i["title"], "points": i["points"],
                       "milestone": i["milestone"], "created": i["created"].isoformat(),
                       "closed": i["closed"].isoformat() if i["closed"] else None,
                       "cycle_hours": i["cycle_hours"]} for i in issues]}
    (METRICS_DIR / "agile-latest.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: m[k] for k in ("cycle_time_hours_median", "current_sprint_points", "avg_velocity", "counts")},
                     ensure_ascii=False, indent=2))
    print(f"✅ 완료: {report.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
