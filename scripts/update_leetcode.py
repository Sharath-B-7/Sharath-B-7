import datetime
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

LEETCODE_USERNAME = "Sharathbcs"
GITHUB_USERNAME = "Sharath-B-7"
GRAPHQL_URL = "https://leetcode.com/graphql"
GITHUB_API_URL = f"https://api.github.com/users/{GITHUB_USERNAME}"
README_PATH = "README.md"
LC_SVG_PATH = "assets/leetcode_stats.svg"
GH_SVG_PATH = "assets/github_stats.svg"

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

headers = {
    "Content-Type": "application/json",
    "User-Agent": DEFAULT_UA,
    "Referer": f"https://leetcode.com/u/{LEETCODE_USERNAME}/",
    "Origin": "https://leetcode.com",
}

GRAPHQL_QUERY = """
query getUserProfile($username: String!) {
  allQuestionsCount {
    difficulty
    count
  }
  matchedUser(username: $username) {
    username
    profile {
      ranking
      reputation
    }
    submitStats {
      acSubmissionNum {
        difficulty
        count
        submissions
      }
    }
    badges {
      id
      displayName
    }
  }
  userContestRanking(username: $username) {
    attendedContestsCount
    rating
    globalRanking
    totalParticipants
    topPercentage
  }
}
"""

REQUIRED_LC_KEYS = (
    "total_solved",
    "total_questions",
    "easy_solved",
    "easy_total",
    "medium_solved",
    "medium_total",
    "hard_solved",
    "hard_total",
    "contest_rating",
    "global_rank",
    "top_percentile",
    "contests_attended",
    "badge_count",
)


def _read_text(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def _parse_int(val):
    return int(str(val).replace(",", "").strip())


def load_existing_lc_stats(readme_path=README_PATH, svg_path=LC_SVG_PATH):
    """Load the latest persisted LeetCode metrics from README.md and leetcode_stats.svg.

    Used as the baseline so partial API failures preserve current live fields
    and full API failures never overwrite synced stats with stale constants.
    """
    existing = {}
    readme = _read_text(readme_path)
    if readme:
        m_rank = re.search(
            r"\|\s*🏆\s*\*\*Global Rank\*\*\s*\|\s*\*\*([\d,]+)\*\*\s*\|\s*Top\s*\*\*([\d.]+%)\*\*",
            readme,
        )
        if m_rank:
            existing["global_rank"] = m_rank.group(1)
            existing["top_percentile"] = m_rank.group(2)

        m_contest = re.search(
            r"\|\s*📈\s*\*\*Contest Rating\*\*\s*\|\s*\*\*([\d,]+)\*\*\s*\|\s*\*\*(\d+)\*\*\s*Contests Attended",
            readme,
        )
        if m_contest:
            existing["contest_rating"] = m_contest.group(1)
            existing["contests_attended"] = int(m_contest.group(2))

        m_solved = re.search(
            r"\|\s*💻\s*\*\*Total Problems Solved\*\*\s*\|\s*\*\*(\d+)\s*/\s*([\d,]+)\*\*\s*\|\s*"
            r"🟢\s*\*\*(\d+)\*\*\s*Easy\s*\\\|\s*🟡\s*\*\*(\d+)\*\*\s*Medium\s*\\\|\s*🔴\s*\*\*(\d+)\*\*\s*Hard",
            readme,
        )
        if m_solved:
            existing["total_solved"] = int(m_solved.group(1))
            existing["total_questions"] = _parse_int(m_solved.group(2))
            existing["easy_solved"] = int(m_solved.group(3))
            existing["medium_solved"] = int(m_solved.group(4))
            existing["hard_solved"] = int(m_solved.group(5))

        m_badges = re.search(
            r"\|\s*🏅\s*\*\*Badges\*\*\s*\|\s*\*\*(\d+)\s+Badges\*\*",
            readme,
        )
        if m_badges:
            existing["badge_count"] = int(m_badges.group(1))

    svg = _read_text(svg_path)
    if svg:
        for key, label in (("easy_total", "Easy"), ("medium_total", "Medium"), ("hard_total", "Hard")):
            m = re.search(
                rf"{label}</span>\s*<span><strong>\d+</strong>\s*/\s*([\d,]+)</span>",
                svg,
            )
            if m:
                existing[key] = _parse_int(m.group(1))

    return existing


def load_existing_github_stats(svg_path=GH_SVG_PATH):
    """Load existing public_repos and followers from github_stats.svg if available."""
    existing = {}
    svg = _read_text(svg_path)
    if not svg:
        return existing
    m_repos = re.search(
        r'class="stat-num">(\d+)</div>\s*<div class="stat-label">[^<]*Public Repositories',
        svg,
    )
    if m_repos:
        existing["public_repos"] = int(m_repos.group(1))
    m_fol = re.search(
        r'class="stat-num">(\d+)</div>\s*<div class="stat-label">[^<]*Followers',
        svg,
    )
    if m_fol:
        existing["followers"] = int(m_fol.group(1))
    return existing


def _fetch_leetcode_graphql(username):
    """Primary source: official LeetCode GraphQL endpoint (single atomic request)."""
    payload = json.dumps({"query": GRAPHQL_QUERY, "variables": {"username": username}}).encode("utf-8")
    for attempt in range(1, 4):
        try:
            print(f"Attempt {attempt}: Fetching LeetCode data from official GraphQL API...")
            req = urllib.request.Request(GRAPHQL_URL, data=payload, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            data = body.get("data") if isinstance(body, dict) else None
            matched = data.get("matchedUser") if isinstance(data, dict) else None
            ac_nums = (matched or {}).get("submitStats", {}).get("acSubmissionNum", [])
            all_solved = next((item.get("count", 0) for item in ac_nums if item.get("difficulty") == "All"), 0)
            if matched and all_solved > 0:
                print("Successfully fetched live LeetCode GraphQL data.")
                return data
            print(f"GraphQL attempt {attempt} returned incomplete payload: {body.get('errors')}", file=sys.stderr)
        except Exception as e:
            print(f"GraphQL attempt {attempt} failed: {e}", file=sys.stderr)
        time.sleep(1.5 * attempt)
    return None


def _fetch_json(url, req_headers, timeout=12):
    req = urllib.request.Request(url, headers=req_headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _fetch_leetcode_alfa_rest(username):
    """Secondary fallback: alfa-leetcode-api with spacing to avoid burst 429s."""
    req_headers = {
        "User-Agent": DEFAULT_UA,
        "Accept": "application/json, text/plain, */*",
    }
    merged = {}
    for attempt in range(1, 3):
        try:
            print(f"Fallback REST (alfa) attempt {attempt}...")
            p_data = _fetch_json(f"https://alfa-leetcode-api.onrender.com/userProfile/{username}", req_headers, 12)
            if not (isinstance(p_data, dict) and (p_data.get("totalSolved") or 0) > 0):
                time.sleep(2)
                continue
            merged.update(p_data)

            time.sleep(1.5)
            try:
                c_data = _fetch_json(f"https://alfa-leetcode-api.onrender.com/{username}/contest", req_headers, 10)
                if isinstance(c_data, dict) and c_data.get("contestRating"):
                    merged["contest"] = c_data
            except Exception as e_c:
                print(f"Alfa contest fetch skipped: {e_c}", file=sys.stderr)

            time.sleep(1.5)
            try:
                b_data = _fetch_json(f"https://alfa-leetcode-api.onrender.com/{username}/badges", req_headers, 10)
                if isinstance(b_data, dict) and b_data.get("badgesCount") is not None:
                    merged["badges_data"] = b_data
            except Exception as e_b:
                print(f"Alfa badges fetch skipped: {e_b}", file=sys.stderr)

            print("Successfully fetched live LeetCode REST (alfa) data.")
            return merged
        except Exception as e:
            print(f"Alfa REST attempt {attempt} failed: {e}", file=sys.stderr)
            time.sleep(2)
    return None


def _fetch_leetcode_faisal_rest(username):
    """Tertiary fallback: faisalshohag Vercel mirror (solved counts & global rank)."""
    req_headers = {"User-Agent": DEFAULT_UA, "Accept": "application/json"}
    try:
        print("Fallback REST (faisalshohag)...")
        data = _fetch_json(f"https://leetcode-api-faisalshohag.vercel.app/{username}", req_headers, 12)
        if isinstance(data, dict) and (data.get("totalSolved") or 0) > 0:
            print("Successfully fetched live LeetCode REST (faisalshohag) data.")
            return data
    except Exception as e:
        print(f"Faisalshohag REST fetch failed: {e}", file=sys.stderr)
    return None


def fetch_leetcode_data(username):
    """Fetch live LeetCode stats using GraphQL first, then REST fallbacks."""
    data = _fetch_leetcode_graphql(username)
    if data:
        return data
    data = _fetch_leetcode_alfa_rest(username)
    if data:
        return data
    return _fetch_leetcode_faisal_rest(username)


def parse_stats(data, existing_stats=None):
    """Parse API payload into normalized metrics, preserving existing live values on partial data.

    Returns None if data is missing or required metrics could not be resolved.
    """
    if not data:
        return None

    stats = dict(existing_stats) if existing_stats else {}

    # Handles REST schemas (alfa-leetcode-api / faisalshohag)
    if "totalSolved" in data and (data.get("totalSolved") or 0) > 0:
        stats["total_solved"] = int(data["totalSolved"])
        if data.get("easySolved") is not None:
            stats["easy_solved"] = int(data["easySolved"])
        if data.get("mediumSolved") is not None:
            stats["medium_solved"] = int(data["mediumSolved"])
        if data.get("hardSolved") is not None:
            stats["hard_solved"] = int(data["hardSolved"])
        if data.get("totalQuestions"):
            stats["total_questions"] = int(data["totalQuestions"])
        if data.get("totalEasy"):
            stats["easy_total"] = int(data["totalEasy"])
        if data.get("totalMedium"):
            stats["medium_total"] = int(data["totalMedium"])
        if data.get("totalHard"):
            stats["hard_total"] = int(data["totalHard"])
        if data.get("ranking"):
            stats["global_rank"] = f"{int(data['ranking']):,}"

    # Extract contest stats from REST merge (only update when actually returned)
    c_data = data.get("contest") if isinstance(data.get("contest"), dict) else data
    c_rating = c_data.get("contestRating")
    if c_rating is not None and c_rating > 0:
        stats["contest_rating"] = f"{int(round(c_rating)):,}"
    c_att = c_data.get("contestAttend")
    if c_att is not None and c_att > 0:
        stats["contests_attended"] = int(c_att)
    top_pct = c_data.get("contestTopPercentage")
    if top_pct is not None and top_pct > 0:
        stats["top_percentile"] = f"{float(top_pct):.2f}%"

    # Extract badges count from REST merge
    b_data = data.get("badges_data") if isinstance(data.get("badges_data"), dict) else data
    if b_data.get("badgesCount") is not None:
        stats["badge_count"] = int(b_data["badgesCount"])

    # Handles official GraphQL schema
    if "allQuestionsCount" in data:
        for q in data.get("allQuestionsCount") or []:
            diff = q.get("difficulty")
            cnt = q.get("count", 0)
            if diff == "All" and cnt:
                stats["total_questions"] = int(cnt)
            elif diff == "Easy" and cnt:
                stats["easy_total"] = int(cnt)
            elif diff == "Medium" and cnt:
                stats["medium_total"] = int(cnt)
            elif diff == "Hard" and cnt:
                stats["hard_total"] = int(cnt)

        matched = data.get("matchedUser") or {}
        for sub in matched.get("submitStats", {}).get("acSubmissionNum", []):
            diff = sub.get("difficulty")
            cnt = sub.get("count")
            if cnt is None:
                continue
            if diff == "All" and cnt > 0:
                stats["total_solved"] = int(cnt)
            elif diff == "Easy":
                stats["easy_solved"] = int(cnt)
            elif diff == "Medium":
                stats["medium_solved"] = int(cnt)
            elif diff == "Hard":
                stats["hard_solved"] = int(cnt)

        badges = matched.get("badges")
        if isinstance(badges, list):
            stats["badge_count"] = len(badges)

        p_rank = matched.get("profile", {}).get("ranking")
        if p_rank:
            stats["global_rank"] = f"{int(p_rank):,}"

        contest = data.get("userContestRanking")
        if isinstance(contest, dict):
            c_rating = contest.get("rating")
            if c_rating:
                stats["contest_rating"] = f"{int(round(c_rating)):,}"
            top_pct = contest.get("topPercentage")
            if top_pct is not None:
                stats["top_percentile"] = f"{float(top_pct):.2f}%"
            c_att = contest.get("attendedContestsCount")
            if c_att is not None:
                stats["contests_attended"] = int(c_att)

    missing = [k for k in REQUIRED_LC_KEYS if k not in stats]
    if missing:
        print(f"Missing required LeetCode fields {missing}; refusing partial overwrite.", file=sys.stderr)
        return None
    return stats


def generate_svg(stats):
    easy_pct = round((stats["easy_solved"] / max(1, stats["easy_total"])) * 100, 1)
    med_pct = round((stats["medium_solved"] / max(1, stats["medium_total"])) * 100, 1)
    hard_pct = round((stats["hard_solved"] / max(1, stats["hard_total"])) * 100, 1)

    svg_content = f"""<svg fill="none" viewBox="0 0 850 336" width="850" height="336" xmlns="http://www.w3.org/2000/svg">
  <foreignObject width="100%" height="100%">
    <div xmlns="http://www.w3.org/1999/xhtml">
      <style>
        .lc-card, .lc-card * {{
          box-sizing: border-box;
        }}

        .lc-card {{
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
          background: linear-gradient(135deg, #0d1117 0%, #161b22 100%);
          border: 1px solid #30363d;
          border-radius: 16px;
          padding: 24px 36px;
          width: 850px;
          height: 336px;
          color: #c9d1d9;
          position: relative;
          overflow: hidden;
          box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
          display: flex;
          flex-direction: column;
        }}

        .lc-header {{
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 18px;
          border-bottom: 1px solid #21262d;
          padding-bottom: 12px;
        }}

        .lc-title {{
          font-size: 20px;
          font-weight: 700;
          color: #f0883e;
          display: flex;
          align-items: center;
          gap: 10px;
        }}

        .lc-user {{
          font-size: 14px;
          color: #8b949e;
          font-family: 'Fira Code', monospace;
          background: #21262d;
          padding: 4px 12px;
          border-radius: 20px;
          border: 1px solid #30363d;
        }}

        .lc-grid {{
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 28px;
          flex: 1;
          min-height: 0;
        }}

        .lc-col {{
          display: flex;
          flex-direction: column;
          gap: 12px;
          height: 100%;
        }}

        .stat-box {{
          background: rgba(22, 27, 34, 0.8);
          border: 1px solid #30363d;
          border-radius: 12px;
          padding: 14px 18px;
        }}

        .diff-row {{
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 6px;
          font-size: 13px;
        }}

        .diff-easy {{ color: #2ecc71; font-weight: 600; }}
        .diff-medium {{ color: #f1c40f; font-weight: 600; }}
        .diff-hard {{ color: #e74c3c; font-weight: 600; }}

        .progress-bar {{
          height: 6px;
          background: #21262d;
          border-radius: 3px;
          overflow: hidden;
        }}

        .progress-fill-easy {{ width: {easy_pct}%; background: #2ecc71; height: 100%; }}
        .progress-fill-medium {{ width: {med_pct}%; background: #f1c40f; height: 100%; }}
        .progress-fill-hard {{ width: {hard_pct}%; background: #e74c3c; height: 100%; }}

        .total-solved {{
          text-align: center;
          background: rgba(240, 136, 62, 0.08);
          border: 1px solid rgba(240, 136, 62, 0.3);
          border-radius: 12px;
          padding: 12px 14px;
        }}

        .total-num {{
          font-size: 34px;
          font-weight: 800;
          color: #f0883e;
          line-height: 1;
        }}

        .total-label {{
          font-size: 12px;
          color: #8b949e;
          margin-top: 4px;
          text-transform: uppercase;
          letter-spacing: 1px;
        }}

        .metric-row {{
          display: flex;
          justify-content: space-between;
          align-items: center;
          font-size: 13px;
          padding: 7px 0;
          border-bottom: 1px dashed #21262d;
        }}

        .metric-row:last-child {{
          border-bottom: none;
        }}

        .metric-label {{ color: #8b949e; }}
        .metric-val {{ color: #f0f6fc; font-weight: 600; font-family: 'Fira Code', monospace; }}
      </style>

      <div class="lc-card">
        <div class="lc-header">
          <div class="lc-title">
            <span>🧠</span> LEETCODE STATISTICS
          </div>
          <div class="lc-user">@{LEETCODE_USERNAME}</div>
        </div>

        <div class="lc-grid">
          <!-- Col 1: Solved & Difficulty -->
          <div class="lc-col">
            <div class="total-solved">
              <div class="total-num">{stats["total_solved"]}</div>
              <div class="total-label">Problems Solved</div>
            </div>

            <div class="stat-box" style="flex: 1; display: flex; flex-direction: column; justify-content: center;">
              <div class="diff-row">
                <span class="diff-easy">🟢 Easy</span>
                <span><strong>{stats["easy_solved"]}</strong> / {stats["easy_total"]:,}</span>
              </div>
              <div class="progress-bar" style="margin-bottom: 10px;">
                <div class="progress-fill-easy"></div>
              </div>

              <div class="diff-row">
                <span class="diff-medium">🟡 Medium</span>
                <span><strong>{stats["medium_solved"]}</strong> / {stats["medium_total"]:,}</span>
              </div>
              <div class="progress-bar" style="margin-bottom: 10px;">
                <div class="progress-fill-medium"></div>
              </div>

              <div class="diff-row">
                <span class="diff-hard">🔴 Hard</span>
                <span><strong>{stats["hard_solved"]}</strong> / {stats["hard_total"]:,}</span>
              </div>
              <div class="progress-bar">
                <div class="progress-fill-hard"></div>
              </div>
            </div>
          </div>

          <!-- Col 2: Rating & Rank -->
          <div class="lc-col">
            <div class="stat-box" style="height: 100%; display: flex; flex-direction: column; justify-content: space-around;">
              <div class="metric-row">
                <span class="metric-label">📈 Contest Rating</span>
                <span class="metric-val" style="color: #f0883e;">{stats["contest_rating"]}</span>
              </div>
              <div class="metric-row">
                <span class="metric-label">🏆 Global Rank</span>
                <span class="metric-val">{stats["global_rank"]}</span>
              </div>
              <div class="metric-row">
                <span class="metric-label">🎯 Top Percentile</span>
                <span class="metric-val" style="color: #2ecc71;">Top {stats["top_percentile"]}</span>
              </div>
              <div class="metric-row">
                <span class="metric-label">🏁 Contests</span>
                <span class="metric-val">{stats["contests_attended"]} Contests</span>
              </div>
              <div class="metric-row">
                <span class="metric-label">🏅 Badges</span>
                <span class="metric-val">{stats["badge_count"]} Badges</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </foreignObject>
</svg>"""
    return svg_content


def fetch_github_data(username, existing_stats=None):
    """Fetch public repo/follower counts via authenticated GitHub REST API when needed."""
    gh_stats = dict(existing_stats) if existing_stats else {}
    req_headers = {"User-Agent": DEFAULT_UA, "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        req_headers["Authorization"] = f"Bearer {token}"
    try:
        req_gh = urllib.request.Request(GITHUB_API_URL, headers=req_headers)
        with urllib.request.urlopen(req_gh, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if isinstance(data, dict) and "public_repos" in data:
            gh_stats["public_repos"] = int(data["public_repos"])
            gh_stats["followers"] = int(data.get("followers", 0))
            gh_stats["following"] = int(data.get("following", 0))
            return gh_stats
    except Exception as e:
        print(f"GitHub REST API fetch failed: {e}", file=sys.stderr)
    return gh_stats if "public_repos" in gh_stats and "followers" in gh_stats else None


def fetch_github_activity(username):
    """Fetch GitHub contribution calendar and profile summary via GraphQL (or HTML fallback).

    Returns (activity_dict, graphql_profile_stats_or_None).
    Returns (None, None) if all contribution sources fail so callers avoid zeroing out stats.
    """
    token = os.environ.get("GITHUB_TOKEN", "")
    daily_counts = {}
    gql_stats = None

    # Primary: GitHub GraphQL API
    if token:
        gql = """
query($username: String!) {
  user(login: $username) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            contributionCount
            date
          }
        }
      }
    }
    repositories(privacy: PUBLIC, first: 1) {
      totalCount
    }
    followers {
      totalCount
    }
    following {
      totalCount
    }
  }
}
"""
        try:
            payload = json.dumps({"query": gql, "variables": {"username": username}}).encode("utf-8")
            req = urllib.request.Request(
                "https://api.github.com/graphql",
                data=payload,
                headers={
                    "Authorization": f"bearer {token}",
                    "Content-Type": "application/json",
                    "User-Agent": DEFAULT_UA,
                },
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            user_node = data["data"]["user"]
            cal = user_node["contributionsCollection"]["contributionCalendar"]
            for week in cal["weeks"]:
                for day in week["contributionDays"]:
                    daily_counts[day["date"]] = day["contributionCount"]

            gql_stats = {
                "public_repos": int(user_node["repositories"]["totalCount"]),
                "followers": int(user_node["followers"]["totalCount"]),
                "following": int(user_node["following"]["totalCount"]),
            }
            print(f"GitHub GraphQL API: {cal['totalContributions']} contributions fetched.")
        except Exception as e:
            print(f"GitHub GraphQL fetch failed: {e}", file=sys.stderr)
            daily_counts = {}

    # Fallback: HTML scraping (mapping id -> for to stay robust to DOM ordering)
    if not daily_counts:
        url = f"https://github.com/users/{username}/contributions"
        req = urllib.request.Request(url, headers={"User-Agent": DEFAULT_UA})
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                html = resp.read().decode("utf-8")

            id_date_pairs = re.findall(
                r'data-date="(\d{4}-\d{2}-\d{2})"[^>]*id="(contribution-day-component-[^"]+)"',
                html,
            )
            id_to_date = {cid: dt for dt, cid in id_date_pairs}
            tt_pairs = re.findall(
                r'<tool-tip[^>]*for="(contribution-day-component-[^"]+)"[^>]*>([\s\S]*?)</tool-tip>',
                html,
            )
            for cid, tip in tt_pairs:
                dt = id_to_date.get(cid)
                if not dt:
                    continue
                tip_clean = tip.strip()
                if "No contributions" in tip_clean:
                    daily_counts[dt] = 0
                else:
                    m = re.search(r"(\d+)\s+contribution", tip_clean)
                    daily_counts[dt] = int(m.group(1)) if m else 0

            if not daily_counts:
                dates = re.findall(r'data-date="(\d{4}-\d{2}-\d{2})"', html)
                tips = re.findall(r"<tool-tip[^>]*>([\s\S]*?)</tool-tip>", html)
                for dt, tip in zip(dates, tips):
                    tip_clean = tip.strip()
                    if "No contributions" in tip_clean:
                        daily_counts[dt] = 0
                    else:
                        m = re.search(r"(\d+)\s+contribution", tip_clean)
                        daily_counts[dt] = int(m.group(1)) if m else 0
            print(f"HTML scrape: {sum(daily_counts.values())} contributions fetched.")
        except Exception as e:
            print(f"HTML scrape failed: {e}", file=sys.stderr)

    if not daily_counts:
        return None, gql_stats

    sorted_dates = sorted(daily_counts.keys())
    total_contribs = sum(daily_counts.values())

    longest_streak, longest_start, longest_end = 0, None, None
    temp_streak, temp_start = 0, None
    for dt in sorted_dates:
        if daily_counts[dt] > 0:
            if temp_streak == 0:
                temp_start = dt
            temp_streak += 1
            if temp_streak > longest_streak:
                longest_streak = temp_streak
                longest_start = temp_start
                longest_end = dt
        else:
            temp_streak = 0
            temp_start = None

    today_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    curr, curr_start, curr_end = 0, None, None
    for dt in reversed(sorted_dates):
        if daily_counts[dt] > 0:
            if curr == 0:
                curr_end = dt
            curr += 1
            curr_start = dt
        elif dt >= today_str and curr == 0:
            continue
        else:
            break

    def fmt_date(d):
        return datetime.datetime.strptime(d, "%Y-%m-%d").strftime("%b %d") if d else ""

    def fmt_range(s, e):
        if not s or not e:
            return ""
        so = datetime.datetime.strptime(s, "%Y-%m-%d")
        eo = datetime.datetime.strptime(e, "%Y-%m-%d")
        if s == e:
            return so.strftime("%b %d")
        if so.month == eo.month:
            return f"{so.strftime('%b %d')} - {eo.strftime('%d')}"
        return f"{so.strftime('%b %d')} - {eo.strftime('%b %d')}"

    date_range_str = (
        f"{fmt_date(sorted_dates[0])}, {sorted_dates[0][:4]} – "
        f"{fmt_date(sorted_dates[-1])}, {sorted_dates[-1][:4]}"
    )
    curr_streak_dates = fmt_range(curr_start, curr_end) if curr > 0 else "Recent"
    longest_streak_dates = fmt_range(longest_start, longest_end) if longest_streak > 0 else "—"

    rects_svg = []
    start_dt = datetime.datetime.strptime(sorted_dates[0], "%Y-%m-%d")
    week_idx = 0
    day_idx = (start_dt.weekday() + 1) % 7
    for dt_str in sorted_dates:
        cnt = daily_counts[dt_str]
        if cnt == 0:
            fill = "#161b22"
        elif cnt == 1:
            fill = "#0e4429"
        elif cnt <= 3:
            fill = "#006d32"
        elif cnt <= 7:
            fill = "#26a641"
        else:
            fill = "#39d353"
        x = week_idx * 8.2
        y = day_idx * 8.2
        rects_svg.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="6.5" height="6.5" rx="1.5" fill="{fill}" />'
        )
        day_idx += 1
        if day_idx == 7:
            day_idx = 0
            week_idx += 1

    activity = {
        "total_contributions": total_contribs,
        "current_streak": curr,
        "current_streak_dates": curr_streak_dates,
        "longest_streak": longest_streak,
        "longest_streak_dates": longest_streak_dates,
        "date_range": date_range_str,
        "heatmap_svg": "".join(rects_svg),
    }
    return activity, gql_stats


def generate_github_svg(act, gh_stats):
    svg_content = f"""<svg fill="none" viewBox="0 0 850 380" width="850" height="380" xmlns="http://www.w3.org/2000/svg">
  <foreignObject width="100%" height="100%">
    <div xmlns="http://www.w3.org/1999/xhtml">
      <style>
        .gh-card, .gh-card * {{
          box-sizing: border-box;
        }}

        .gh-card {{
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
          background: linear-gradient(135deg, #0d1117 0%, #161b22 100%);
          border: 1px solid #30363d;
          border-radius: 16px;
          padding: 24px 32px;
          width: 850px;
          height: 380px;
          color: #c9d1d9;
          position: relative;
          overflow: hidden;
          box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
          display: flex;
          flex-direction: column;
          justify-content: space-between;
        }}

        .gh-header {{
          display: flex;
          justify-content: space-between;
          align-items: center;
          border-bottom: 1px solid #21262d;
          padding-bottom: 12px;
        }}

        .gh-title {{
          font-size: 20px;
          font-weight: 700;
          color: #38bdf8;
          display: flex;
          align-items: center;
          gap: 10px;
        }}

        .gh-user {{
          font-size: 14px;
          color: #8b949e;
          font-family: 'Fira Code', monospace;
          background: #21262d;
          padding: 4px 12px;
          border-radius: 20px;
          border: 1px solid #30363d;
        }}

        .contrib-grid {{
          display: grid;
          grid-template-columns: 1.4fr 1fr;
          gap: 20px;
        }}

        .contrib-box {{
          background: rgba(22, 27, 34, 0.8);
          border: 1px solid #30363d;
          border-radius: 12px;
          padding: 16px 20px;
          display: flex;
          flex-direction: column;
          justify-content: space-between;
        }}

        .contrib-header-label {{
          font-size: 12px;
          font-weight: 700;
          color: #8b949e;
          text-transform: uppercase;
          letter-spacing: 0.8px;
        }}

        .total-contrib-num {{
          font-size: 34px;
          font-weight: 800;
          color: #38bdf8;
          font-family: 'Fira Code', monospace;
          line-height: 1.1;
          margin-top: 4px;
        }}

        .contrib-date-subtext {{
          font-size: 11px;
          color: #8b949e;
          margin-top: 2px;
          margin-bottom: 8px;
        }}

        .streak-row {{
          display: flex;
          align-items: center;
          justify-content: space-between;
          background: rgba(13, 17, 23, 0.6);
          border: 1px solid #21262d;
          border-radius: 10px;
          padding: 10px 16px;
        }}

        .streak-info {{
          display: flex;
          flex-direction: column;
        }}

        .streak-label {{
          font-size: 11px;
          font-weight: 700;
          color: #8b949e;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }}

        .streak-val {{
          font-size: 22px;
          font-weight: 800;
          font-family: 'Fira Code', monospace;
          display: flex;
          align-items: center;
          gap: 6px;
        }}

        .streak-dates {{
          font-size: 11px;
          color: #8b949e;
        }}

        .analytics-grid {{
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 20px;
        }}

        .stat-card {{
          background: rgba(22, 27, 34, 0.8);
          border: 1px solid #30363d;
          border-radius: 12px;
          padding: 14px 16px;
          text-align: center;
        }}

        .stat-num {{
          font-size: 24px;
          font-weight: 800;
          color: #38bdf8;
          font-family: 'Fira Code', monospace;
        }}

        .stat-label {{
          font-size: 11px;
          color: #8b949e;
          margin-top: 4px;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }}
      </style>

      <div class="gh-card">
        <div class="gh-header">
          <div class="gh-title">
            <span>📊</span> GITHUB ANALYTICS &amp; ACTIVITY
          </div>
          <div class="gh-user">@{GITHUB_USERNAME}</div>
        </div>

        <!-- Top Section: Contribution Activity & Streaks -->
        <div class="contrib-grid">
          <!-- Left: Total Contributions & Heatmap -->
          <div class="contrib-box">
            <div>
              <div class="contrib-header-label">Total Contributions</div>
              <div class="total-contrib-num">{act["total_contributions"]}</div>
              <div class="contrib-date-subtext">{act["date_range"]}</div>
            </div>
            <div style="overflow: hidden; padding-top: 2px;">
              <svg width="445" height="58" viewBox="0 0 445 58">
                {act["heatmap_svg"]}
              </svg>
            </div>
          </div>

          <!-- Right: Current & Longest Streaks -->
          <div class="contrib-box" style="justify-content: space-around;">
            <div class="streak-row">
              <div class="streak-info">
                <span class="streak-label">Current Streak</span>
                <span class="streak-dates">{act["current_streak_dates"]}</span>
              </div>
              <div class="streak-val" style="color: #f0883e;">
                🔥 {act["current_streak"]}
              </div>
            </div>

            <div class="streak-row">
              <div class="streak-info">
                <span class="streak-label">Longest Streak</span>
                <span class="streak-dates">{act["longest_streak_dates"]}</span>
              </div>
              <div class="streak-val" style="color: #2ecc71;">
                ⚡ {act["longest_streak"]}
              </div>
            </div>
          </div>
        </div>

        <!-- Bottom Section: Quick Analytics Summary -->
        <div class="analytics-grid">
          <div class="stat-card">
            <div class="stat-num">{gh_stats["public_repos"]}</div>
            <div class="stat-label">📦 Public Repositories</div>
          </div>
          <div class="stat-card">
            <div class="stat-num">{gh_stats["followers"]}</div>
            <div class="stat-label">👥 Followers</div>
          </div>
        </div>
      </div>
    </div>
  </foreignObject>
</svg>"""
    return svg_content


def _strip_conflict_markers(content):
    """Remove ALL git conflict markers and deduplicate consecutive img lines."""
    two_way = re.compile(
        r"<<<<<<< HEAD\n(.*?)\n=======\n(.*?)\n>>>>>>> [^\n]+\n",
        re.DOTALL,
    )
    for _ in range(10):
        if not two_way.search(content):
            break
        content = two_way.sub(lambda m: m.group(2) + "\n", content)

    content = re.sub(r"^<<<<<<< .*\n", "", content, flags=re.MULTILINE)
    content = re.sub(r"^=======\n", "", content, flags=re.MULTILINE)
    content = re.sub(r"^>>>>>>> .*\n", "", content, flags=re.MULTILINE)

    def dedup_block(m):
        lines = m.group(1).splitlines(keepends=True)
        deduped = []
        for line in lines:
            if deduped and line.strip() and deduped[-1].strip() == line.strip():
                continue
            deduped.append(line)
        tag_open = m.group(0)[: m.start(1) - m.start(0)]
        return tag_open + "".join(deduped) + "</p>"

    return re.sub(r"<p[^>]*>([\s\S]*?)</p>", dedup_block, content)


def _write_if_changed(path, new_content):
    """Write file only when content differs from disk; return True if updated."""
    if _read_text(path) == new_content:
        return False
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)
    return True


def update_readme_table(readme_path, stats, lc_svg_updated=False, gh_svg_updated=False):
    """Update README.md with latest stats and bust cache only for SVGs that actually changed."""
    try:
        original = _read_text(readme_path)
        content = _strip_conflict_markers(original)
        timestamp = int(time.time())

        if lc_svg_updated:
            content = re.sub(
                r'src="\./assets/leetcode_stats\.svg(?:\?v=\d+)?"',
                f'src="./assets/leetcode_stats.svg?v={timestamp}"',
                content,
            )
        elif 'src="./assets/leetcode_stats.svg"' in content:
            content = content.replace(
                'src="./assets/leetcode_stats.svg"',
                f'src="./assets/leetcode_stats.svg?v={timestamp}"',
            )

        if gh_svg_updated:
            content = re.sub(
                r'src="\./assets/github_stats\.svg(?:\?v=\d+)?"',
                f'src="./assets/github_stats.svg?v={timestamp}"',
                content,
            )
        elif 'src="./assets/github_stats.svg"' in content:
            content = content.replace(
                'src="./assets/github_stats.svg"',
                f'src="./assets/github_stats.svg?v={timestamp}"',
            )

        if stats is not None:
            new_table_rows = (
                f'| 🏆 **Global Rank** | **{stats["global_rank"]}** | Top **{stats["top_percentile"]}** worldwide |\n'
                f'| 📈 **Contest Rating** | **{stats["contest_rating"]}** | **{stats["contests_attended"]}** Contests Attended |\n'
                f'| 💻 **Total Problems Solved** | **{stats["total_solved"]} / {stats["total_questions"]:,}** | 🟢 **{stats["easy_solved"]}** Easy \\| 🟡 **{stats["medium_solved"]}** Medium \\| 🔴 **{stats["hard_solved"]}** Hard |\n'
                f'| 🏅 **Badges** | **{stats["badge_count"]} Badges** | Profile: [@Sharathbcs](https://leetcode.com/u/Sharathbcs/) |'
            )

            table_pattern = (
                r"(\| Metric \| Verified Current Figure \| Detail Breakdown \|"
                r"[\s\S]*?\| .* \*\*Badges\*\* \|[\s\S]*?\n)"
            )
            replacement = (
                "| Metric | Verified Current Figure | Detail Breakdown |\n"
                "| :--- | :---: | :--- |\n"
                + new_table_rows
                + "\n"
            )
            content = re.sub(table_pattern, replacement, content)

            content = re.sub(
                r"Solved \*\*\d+ LeetCode Problems\*\*",
                f'Solved **{stats["total_solved"]} LeetCode Problems**',
                content,
            )

        if content != original:
            with open(readme_path, "w", encoding="utf-8") as f:
                f.write(content)
            print("Updated README.md with latest statistics.")
        else:
            print("README.md already up to date.")
    except Exception as e:
        print(f"Error updating README.md: {e}", file=sys.stderr)


def main():
    existing_lc = load_existing_lc_stats(README_PATH, LC_SVG_PATH)
    existing_gh = load_existing_github_stats(GH_SVG_PATH)

    print(f"Fetching LeetCode data for username: {LEETCODE_USERNAME}...")
    raw_data = fetch_leetcode_data(LEETCODE_USERNAME)
    stats = parse_stats(raw_data, existing_stats=existing_lc)

    lc_svg_updated = False
    if stats is not None:
        print(f"Parsed LeetCode Statistics: {stats}")
        lc_svg = generate_svg(stats)
        lc_svg_updated = _write_if_changed(LC_SVG_PATH, lc_svg)
        print(f"{'Updated' if lc_svg_updated else 'Unchanged'}: {LC_SVG_PATH}")
    else:
        print(
            "WARNING: Live LeetCode fetch failed across all APIs; preserving existing LeetCode stats untouched.",
            file=sys.stderr,
        )

    print(f"Fetching GitHub activity & stats for username: {GITHUB_USERNAME}...")
    gh_activity, gql_gh_stats = fetch_github_activity(GITHUB_USERNAME)
    gh_stats = gql_gh_stats or fetch_github_data(GITHUB_USERNAME, existing_stats=existing_gh)

    gh_svg_updated = False
    if gh_activity is not None and gh_stats is not None:
        print(f"Parsed GitHub Stats: {gh_stats}")
        print(
            f"Parsed GitHub Activity: Total={gh_activity['total_contributions']}, "
            f"CurrentStreak={gh_activity['current_streak']}, "
            f"LongestStreak={gh_activity['longest_streak']}"
        )
        gh_svg = generate_github_svg(gh_activity, gh_stats)
        gh_svg_updated = _write_if_changed(GH_SVG_PATH, gh_svg)
        print(f"{'Updated' if gh_svg_updated else 'Unchanged'}: {GH_SVG_PATH}")
    else:
        print(
            "WARNING: GitHub fetch incomplete; preserving existing github_stats.svg untouched.",
            file=sys.stderr,
        )

    update_readme_table(
        README_PATH,
        stats=stats,
        lc_svg_updated=lc_svg_updated,
        gh_svg_updated=gh_svg_updated,
    )


if __name__ == "__main__":
    main()
