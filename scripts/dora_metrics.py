"""
DORA 4대 지표 자동 수집 스크립트
================================

GitHub Actions의 "Deploy" 워크플로우 실행 기록을 읽어서
DORA 4대 지표를 계산하고, 결과를 파일로 남긴다.

  1) Deployment Frequency  배포 빈도      : 성공한 배포 횟수 / 주
  2) Lead Time for Changes 변경 리드타임  : 커밋 시각 → 그 커밋이 배포된 시각
  3) Change Failure Rate   변경 실패율    : 실패한 배포 / 전체 배포
  4) MTTR                  평균 복구 시간 : 배포 실패 → 다음 배포 성공까지 걸린 시간

만들어지는 파일
  metrics/dora-latest.json   이번 계산 결과 (지표 + 배포 목록)
  metrics/history.json       실행할 때마다 쌓이는 지표 기록 (추세 비교용)
  metrics/dora-dashboard.png 대시보드 이미지 (README에 첨부)
  reports/weekly-YYYY-Www.md 주간 보고서
  README.md                  <!-- DORA:START --> ~ <!-- DORA:END --> 구간 자동 갱신

실행
  GitHub Actions 안에서:  python scripts/dora_metrics.py   (REPO, GITHUB_TOKEN 필요)
  내 컴퓨터에서 연습용:    python scripts/dora_metrics.py --mock
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

# ── 설정 ────────────────────────────────────────────────────
WORKFLOW_FILE = "deploy.yml"      # 배포 워크플로우 파일 이름
WINDOW_DAYS = 30                  # 최근 며칠 동안의 기록으로 계산할지
KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
METRICS_DIR = ROOT / "metrics"
REPORTS_DIR = ROOT / "reports"
README = ROOT / "README.md"

# 차트 색상 (색약 검증 통과한 조합)
C = {
    "surface": "#fcfcfb", "ink": "#0b0b0b", "ink2": "#52514e", "muted": "#898781",
    "grid": "#e1e0d9", "axis": "#c3c2b7", "blue": "#2a78d6", "fail": "#d03b3b",
    "tile": "#f4f3ef",
}


# ── GitHub API ──────────────────────────────────────────────
def gh(path: str) -> dict:
    url = f"https://api.github.com{path}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def fetch_deploys(repo: str, since: datetime) -> list[dict]:
    """Deploy 워크플로우의 완료된 실행 기록을 오래된 순으로 가져온다."""
    runs, page = [], 1
    while True:
        data = gh(f"/repos/{repo}/actions/workflows/{WORKFLOW_FILE}/runs"
                  f"?status=completed&per_page=100&page={page}")
        batch = data.get("workflow_runs", [])
        for r in batch:
            if r["conclusion"] not in ("success", "failure"):
                continue  # 취소(cancelled)·건너뜀(skipped)은 제외
            finished = parse_ts(r["updated_at"])
            if finished < since:
                continue
            runs.append({
                "run_number": r["run_number"],
                "sha": r["head_sha"],
                "conclusion": r["conclusion"],
                "event": r["event"],
                "finished_at": finished,
                "head_commit_at": parse_ts(r["head_commit"]["timestamp"]) if r.get("head_commit") else finished,
                "title": (r.get("display_title") or "").split("\n")[0][:60],
                "url": r["html_url"],
            })
        if len(batch) < 100 or page >= 10:
            break
        page += 1
    runs.sort(key=lambda x: x["finished_at"])
    return runs


def attach_commit_times(repo: str, deploys: list[dict]) -> None:
    """각 성공 배포에 '이번에 새로 배포된 커밋들의 작성 시각'을 붙인다."""
    prev_sha = None
    for d in deploys:
        if d["conclusion"] != "success":
            continue
        times = []
        if prev_sha and prev_sha != d["sha"]:
            try:
                cmp = gh(f"/repos/{repo}/compare/{prev_sha}...{d['sha']}")
                times = [parse_ts(c["commit"]["author"]["date"]) for c in cmp.get("commits", [])]
            except Exception as e:  # 강제 push 등으로 비교 불가하면 head 커밋만 사용
                print(f"  compare 실패({e}) → head 커밋 시각만 사용")
        if not times:
            times = [d["head_commit_at"]]
        d["commit_times"] = times
        prev_sha = d["sha"]


# ── 연습용 가짜 데이터 (--mock) ──────────────────────────────
def mock_deploys(now: datetime) -> list[dict]:
    random.seed(7)
    out, t, n = [], now - timedelta(days=20), 1
    while t < now:
        t += timedelta(hours=random.choice([5, 9, 14, 20, 30, 44]))
        if t >= now:
            break
        ok = random.random() > 0.15
        commits = [t - timedelta(hours=random.uniform(0.3, 30)) for _ in range(random.randint(1, 3))]
        out.append({"run_number": n, "sha": f"{n:07x}", "conclusion": "success" if ok else "failure",
                    "event": "push", "finished_at": t, "head_commit_at": max(commits),
                    "commit_times": commits if ok else None, "title": f"mock change #{n}", "url": "#"})
        n += 1
    return out


# ── 지표 계산 ───────────────────────────────────────────────
def hours(td: timedelta) -> float:
    return td.total_seconds() / 3600


def compute(deploys: list[dict], now: datetime, window_days: int) -> dict:
    ok = [d for d in deploys if d["conclusion"] == "success"]
    bad = [d for d in deploys if d["conclusion"] == "failure"]

    # 1) 배포 빈도: 첫 배포 이후 기간 기준 (최소 1일) → 주당 횟수
    if deploys:
        span_days = max(1.0, (now - deploys[0]["finished_at"]).total_seconds() / 86400)
        span_days = min(span_days, window_days)
    else:
        span_days = window_days
    per_week = len(ok) / span_days * 7

    # 2) 리드타임: (배포 완료 - 커밋 작성) 의 중앙값
    lead = []
    for d in ok:
        for ct in d.get("commit_times") or []:
            lead.append(max(0.0, hours(d["finished_at"] - ct)))
    for d in ok:
        lt = [max(0.0, hours(d["finished_at"] - ct)) for ct in (d.get("commit_times") or [])]
        d["lead_hours"] = round(median(lt), 2) if lt else None
    lead_median = round(median(lead), 2) if lead else None

    # 3) 변경 실패율
    cfr = round(len(bad) / len(deploys) * 100, 1) if deploys else None

    # 4) MTTR: 실패 → 다음 성공까지 (연속 실패는 첫 실패부터 잼)
    restores, broken_since = [], None
    for d in deploys:
        if d["conclusion"] == "failure" and broken_since is None:
            broken_since = d["finished_at"]
        elif d["conclusion"] == "success" and broken_since is not None:
            restores.append(hours(d["finished_at"] - broken_since))
            broken_since = None
    mttr = round(sum(restores) / len(restores), 2) if restores else None

    return {
        "deployment_frequency_per_week": round(per_week, 2),
        "lead_time_hours_median": lead_median,
        "change_failure_rate_pct": cfr,
        "mttr_hours": mttr,
        "counts": {"total": len(deploys), "success": len(ok), "failure": len(bad),
                   "restores": len(restores), "currently_failing": broken_since is not None},
        "window_days": window_days,
        "span_days": round(span_days, 2),
    }


# DORA 리포트 기준 성과 등급 (Elite / High / Medium / Low)
def level(metric: str, v) -> str:
    if v is None:
        return "N/A"
    if metric == "df":     # 주당 배포 횟수
        return "Elite" if v >= 7 else "High" if v >= 1 else "Medium" if v >= 0.25 else "Low"
    if metric == "lt":     # 시간
        return "Elite" if v < 24 else "High" if v < 24 * 7 else "Medium" if v < 24 * 30 else "Low"
    if metric == "cfr":    # %
        return "Elite" if v <= 5 else "High" if v <= 15 else "Medium" if v <= 30 else "Low"
    if metric == "mttr":   # 시간
        return "Elite" if v < 1 else "High" if v < 24 else "Medium" if v < 24 * 7 else "Low"
    return "N/A"


def fmt_hours(h) -> str:
    if h is None:
        return "N/A"
    if h < 1:
        return f"{h * 60:.0f} min"
    if h < 48:
        return f"{h:.1f} h"
    return f"{h / 24:.1f} d"


# ── 대시보드 이미지 ─────────────────────────────────────────
def draw_dashboard(m: dict, deploys: list[dict], now: datetime, path: Path) -> None:
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 10,
        "axes.edgecolor": C["axis"], "axes.labelcolor": C["ink2"],
        "xtick.color": C["muted"], "ytick.color": C["muted"],
    })
    fig = plt.figure(figsize=(12, 6.8), dpi=150, facecolor=C["surface"])
    fig.text(0.04, 0.945, "DORA Metrics Dashboard", fontsize=17, fontweight="bold", color=C["ink"])
    fig.text(0.04, 0.905, f"Last {m['window_days']} days  ·  updated {now.astimezone(KST):%Y-%m-%d %H:%M} KST"
             f"  ·  {m['counts']['total']} deploys ({m['counts']['failure']} failed)",
             fontsize=9.5, color=C["ink2"])

    # ① KPI 타일 4개
    tiles = [
        ("Deployment frequency", f"{m['deployment_frequency_per_week']:.1f}", "/ week",
         level("df", m["deployment_frequency_per_week"])),
        ("Lead time for changes", fmt_hours(m["lead_time_hours_median"]), "median",
         level("lt", m["lead_time_hours_median"])),
        ("Change failure rate", "N/A" if m["change_failure_rate_pct"] is None
         else f"{m['change_failure_rate_pct']:.0f}%", "of deploys", level("cfr", m["change_failure_rate_pct"])),
        ("Time to restore (MTTR)", fmt_hours(m["mttr_hours"]), "mean", level("mttr", m["mttr_hours"])),
    ]
    x0, w, gap, y0, h = 0.04, 0.215, 0.0133, 0.66, 0.2
    for i, (label, value, unit, lv) in enumerate(tiles):
        x = x0 + i * (w + gap)
        fig.patches.append(FancyBboxPatch((x, y0), w, h, boxstyle="round,pad=0,rounding_size=0.012",
                                          transform=fig.transFigure, facecolor=C["tile"],
                                          edgecolor="none", zorder=0))
        fig.text(x + 0.015, y0 + h - 0.045, label, fontsize=10, color=C["ink2"])
        fig.text(x + 0.015, y0 + 0.05, value, fontsize=26, fontweight="bold", color=C["ink"])
        fig.text(x + w - 0.015, y0 + 0.058, f"{unit}\n{lv}", fontsize=9, color=C["muted"],
                 ha="right", linespacing=1.5)

    # 기간: 첫 배포일 ~ 오늘 (최소 7일)
    end = now.astimezone(KST).date()
    start = end - timedelta(days=6)
    if deploys:
        start = min(start, deploys[0]["finished_at"].astimezone(KST).date())
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]

    # ② 일별 배포 (성공 / 실패 누적 막대)
    ax1 = fig.add_axes([0.06, 0.1, 0.42, 0.44])
    s_cnt = [sum(1 for d in deploys if d["conclusion"] == "success"
                 and d["finished_at"].astimezone(KST).date() == day) for day in days]
    f_cnt = [sum(1 for d in deploys if d["conclusion"] == "failure"
                 and d["finished_at"].astimezone(KST).date() == day) for day in days]
    xs = list(range(len(days)))
    bw = 0.6
    ax1.bar(xs, s_cnt, width=bw, color=C["blue"], label="Success", zorder=3)
    ax1.bar(xs, f_cnt, width=bw, bottom=s_cnt, color=C["fail"], label="Failure", zorder=3,
            edgecolor=C["surface"], linewidth=1.5)
    ax1.set_title("Deploys per day", loc="left", fontsize=11, color=C["ink"], pad=10)
    step = max(1, len(days) // 7)
    ax1.set_xticks(xs[::step], [d.strftime("%m/%d") for d in days][::step])
    ax1.set_ylim(0, max(2, max((a + b for a, b in zip(s_cnt, f_cnt)), default=0) + 1))
    ax1.yaxis.get_major_locator().set_params(integer=True)
    ax1.legend(loc="upper left", frameon=False, fontsize=9, ncol=2, labelcolor=C["ink2"])

    # ③ 배포별 리드타임
    ax2 = fig.add_axes([0.56, 0.1, 0.40, 0.44])
    pts = [(d["run_number"], d["lead_hours"]) for d in deploys
           if d["conclusion"] == "success" and d.get("lead_hours") is not None]
    unit_label = "hours"
    if pts:
        runs, ty = zip(*pts)
        tx = list(range(len(runs)))
        med = m["lead_time_hours_median"]
        if max(ty) < 2:  # 2시간 미만이면 분 단위로 표시
            ty = [v * 60 for v in ty]
            med = None if med is None else med * 60
            unit_label = "minutes"
        ax2.plot(tx, ty, color=C["blue"], linewidth=2, solid_capstyle="round", zorder=3)
        ax2.scatter(tx, ty, s=34, color=C["blue"], edgecolors=C["surface"], linewidths=2, zorder=4)
        if med is not None:
            ax2.axhline(med, color=C["muted"], linewidth=1, zorder=2)
            ax2.text(0.01, med, f"median {fmt_hours(m['lead_time_hours_median'])}",
                     transform=ax2.get_yaxis_transform(), va="bottom", ha="left",
                     fontsize=8.5, color=C["ink2"])
        ax2.set_ylim(0, max(1.0, max(ty) * 1.25))
        ax2.set_xlim(-0.6, len(tx) - 0.4)
        step = max(1, len(tx) // 8)
        ax2.set_xticks(tx[::step], [f"#{r}" for r in runs][::step])
        ax2.set_xlabel("Deploy run", fontsize=9, color=C["muted"])
    else:
        ax2.text(0.5, 0.5, "No successful deploys yet", ha="center", va="center",
                 transform=ax2.transAxes, color=C["muted"])
        ax2.set_xticks([]); ax2.set_yticks([])
    ax2.set_title(f"Lead time per deploy ({unit_label})", loc="left", fontsize=11, color=C["ink"], pad=10)

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
LEVEL_KO = {"Elite": "🟢 Elite", "High": "🔵 High", "Medium": "🟡 Medium", "Low": "🔴 Low", "N/A": "⚪ N/A"}


def delta_text(cur, prev, unit="", lower_is_better=False) -> str:
    if cur is None or prev is None:
        return "—"
    diff = cur - prev
    if abs(diff) < 1e-9:
        return "변화 없음"
    better = (diff < 0) if lower_is_better else (diff > 0)
    arrow = "▲" if diff > 0 else "▼"
    return f"{arrow} {abs(diff):.1f}{unit} ({'개선' if better else '악화'})"


def metric_rows(m: dict, prev: dict | None) -> list[str]:
    p = prev or {}
    return [
        "| 지표 | 값 | 성과 등급 | 지난 측정 대비 |",
        "|---|---|---|---|",
        f"| 🚀 배포 빈도 (Deployment Frequency) | **{m['deployment_frequency_per_week']:.1f}회 / 주** "
        f"| {LEVEL_KO[level('df', m['deployment_frequency_per_week'])]} "
        f"| {delta_text(m['deployment_frequency_per_week'], p.get('deployment_frequency_per_week'), '회')} |",
        f"| ⏱️ 변경 리드타임 (Lead Time for Changes) | **{fmt_hours(m['lead_time_hours_median'])}** (중앙값) "
        f"| {LEVEL_KO[level('lt', m['lead_time_hours_median'])]} "
        f"| {delta_text(m['lead_time_hours_median'], p.get('lead_time_hours_median'), 'h', True)} |",
        f"| 💥 변경 실패율 (Change Failure Rate) | **"
        f"{'N/A' if m['change_failure_rate_pct'] is None else str(m['change_failure_rate_pct']) + '%'}** "
        f"| {LEVEL_KO[level('cfr', m['change_failure_rate_pct'])]} "
        f"| {delta_text(m['change_failure_rate_pct'], p.get('change_failure_rate_pct'), '%p', True)} |",
        f"| 🛠️ 평균 복구 시간 (MTTR) | **{fmt_hours(m['mttr_hours'])}** "
        f"| {LEVEL_KO[level('mttr', m['mttr_hours'])]} "
        f"| {delta_text(m['mttr_hours'], p.get('mttr_hours'), 'h', True)} |",
    ]


def write_report(m: dict, deploys: list[dict], prev: dict | None, now: datetime) -> Path:
    kst = now.astimezone(KST)
    iso_year, iso_week, _ = kst.isocalendar()
    path = REPORTS_DIR / f"weekly-{iso_year}-W{iso_week:02d}.md"
    week_start = (kst - timedelta(days=kst.weekday())).date()

    lines = [
        f"# 📊 DORA 주간 보고서 — {iso_year}년 {iso_week}주차",
        "",
        f"> 기간: {week_start} ~ {week_start + timedelta(days=6)} · 생성: {kst:%Y-%m-%d %H:%M} KST · "
        f"계산 범위: 최근 {m['window_days']}일 · 자동 생성 (GitHub Actions)",
        "",
        "![DORA dashboard](../metrics/dora-dashboard.png)",
        "",
        "## 1. 핵심 지표",
        "",
        *metric_rows(m, prev),
        "",
        f"- 전체 배포 **{m['counts']['total']}회** (성공 {m['counts']['success']} · 실패 {m['counts']['failure']}), "
        f"복구 {m['counts']['restores']}회",
    ]
    if m["counts"]["currently_failing"]:
        lines.append("- ⚠️ **현재 마지막 배포가 실패 상태**입니다. 복구 배포가 필요합니다.")

    lines += ["", "## 2. 이번 주 배포 기록", ""]
    this_week = [d for d in deploys if d["finished_at"].astimezone(KST).date() >= week_start]
    if this_week:
        lines += ["| # | 완료 시각 (KST) | 결과 | 커밋 | 리드타임 |", "|---|---|---|---|---|"]
        for d in reversed(this_week):
            res = "✅ 성공" if d["conclusion"] == "success" else "❌ 실패"
            lt = fmt_hours(d.get("lead_hours")) if d["conclusion"] == "success" else "—"
            lines.append(f"| [{d['run_number']}]({d['url']}) | {d['finished_at'].astimezone(KST):%m-%d %H:%M} "
                         f"| {res} | `{d['sha'][:7]}` {d['title']} | {lt} |")
    else:
        lines.append("이번 주에는 배포가 없었습니다.")

    lines += ["", "## 3. 해석 및 다음 주 액션", ""]
    tips = []
    if level("df", m["deployment_frequency_per_week"]) in ("Medium", "Low"):
        tips.append("배포 빈도가 낮습니다 → 작업을 작은 단위(PR)로 나눠 자주 main에 병합하기")
    if m["lead_time_hours_median"] and m["lead_time_hours_median"] >= 24:
        tips.append("리드타임이 하루 이상입니다 → 커밋 후 바로 push 하고, PR 리뷰 대기 시간을 줄이기")
    if m["change_failure_rate_pct"] and m["change_failure_rate_pct"] > 15:
        tips.append("실패율이 15%를 넘습니다 → 배포 전 테스트(CI) 강화하기 (7·12주차 과제와 연계)")
    if m["mttr_hours"] and m["mttr_hours"] >= 1:
        tips.append("복구에 1시간 이상 걸립니다 → 실패 원인 기록·롤백 절차 문서화하기")
    if not tips:
        tips.append("모든 지표가 양호합니다 → 현재 흐름을 유지하며 기능 개발 속도를 높이기")
    lines += [f"- {t}" for t in tips]
    lines += ["", "---", "<sub>이 보고서는 `scripts/dora_metrics.py`가 Deploy 워크플로우 기록을 분석해 자동으로 생성했습니다.</sub>", ""]

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def update_readme(m: dict, prev: dict | None, report: Path, now: datetime) -> None:
    block = "\n".join([
        "<!-- DORA:START -->",
        "## 📊 DORA 지표 (자동 갱신)",
        "",
        f"> 최근 갱신: {now.astimezone(KST):%Y-%m-%d %H:%M} KST · "
        f"[최신 주간 보고서]({report.relative_to(ROOT).as_posix()}) · "
        "[원본 JSON](metrics/dora-latest.json)",
        "",
        "![DORA dashboard](metrics/dora-dashboard.png)",
        "",
        *metric_rows(m, prev),
        "<!-- DORA:END -->",
    ])
    text = README.read_text(encoding="utf-8") if README.exists() else "# ossproject\n"
    if "<!-- DORA:START -->" in text:
        text = re.sub(r"<!-- DORA:START -->.*?<!-- DORA:END -->", lambda _: block, text, flags=re.S)
    else:
        text = text.rstrip() + "\n\n" + block + "\n"
    README.write_text(text, encoding="utf-8")


# ── 실행 ────────────────────────────────────────────────────
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true", help="GitHub 없이 가짜 데이터로 연습 실행")
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    since = now - timedelta(days=WINDOW_DAYS)

    if args.mock:
        deploys = mock_deploys(now)
    else:
        repo = os.environ["REPO"]
        print(f"📥 {repo} 의 배포 기록 수집 중...")
        deploys = fetch_deploys(repo, since)
        attach_commit_times(repo, deploys)
    print(f"  배포 {len(deploys)}건")

    m = compute(deploys, now, WINDOW_DAYS)

    METRICS_DIR.mkdir(exist_ok=True)
    hist_path = METRICS_DIR / "history.json"
    history = json.loads(hist_path.read_text(encoding="utf-8")) if hist_path.exists() else []
    prev = history[-1]["metrics"] if history else None

    draw_dashboard(m, deploys, now, METRICS_DIR / "dora-dashboard.png")
    report = write_report(m, deploys, prev, now)
    update_readme(m, prev, report, now)

    snapshot = {"generated_at": now.isoformat(timespec="seconds"), "metrics": m,
                "levels": {"deployment_frequency": level("df", m["deployment_frequency_per_week"]),
                           "lead_time": level("lt", m["lead_time_hours_median"]),
                           "change_failure_rate": level("cfr", m["change_failure_rate_pct"]),
                           "mttr": level("mttr", m["mttr_hours"])}}
    history.append(snapshot)
    hist_path.write_text(json.dumps(history[-200:], ensure_ascii=False, indent=2), encoding="utf-8")

    latest = dict(snapshot)
    latest["deploys"] = [{
        "run_number": d["run_number"], "sha": d["sha"], "conclusion": d["conclusion"],
        "finished_at": d["finished_at"].isoformat(), "lead_hours": d.get("lead_hours"), "url": d["url"],
    } for d in deploys]
    (METRICS_DIR / "dora-latest.json").write_text(json.dumps(latest, ensure_ascii=False, indent=2),
                                                  encoding="utf-8")
    print(json.dumps(snapshot["metrics"], ensure_ascii=False, indent=2))
    print(f"✅ 완료: {report.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
