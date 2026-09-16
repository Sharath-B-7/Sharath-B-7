import json
import re
import sys
import time
import urllib.request

LEETCODE_USERNAME = "Sharathbcs"
GITHUB_USERNAME = "Sharath-B-7"
GRAPHQL_URL = "https://leetcode.com/graphql"
REST_API_URL = f"https://alfa-leetcode-api.onrender.com/userProfile/{LEETCODE_USERNAME}"
GITHUB_API_URL = f"https://api.github.com/users/{GITHUB_USERNAME}"

headers = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://leetcode.com",
}

graphql_query = """
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
  userContestRanking(userSlug: $username) {
    attendedContestsCount
    rating
    globalRanking
    totalParticipants
    topPercentage
  }
}
"""

def fetch_leetcode_data(username):
    url = f"https://alfa-leetcode-api.onrender.com/userProfile/{username}"
    for attempt in range(1, 4):
        try:
            print(f"Attempt {attempt}: Fetching LeetCode data from {url}...")
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                if res and "totalSolved" in res:
                    print("Successfully fetched live data via LeetCode REST API.")
                    return res
        except Exception as e:
            print(f"Attempt {attempt} failed: {e}", file=sys.stderr)
            time.sleep(2)

    return None

def fetch_github_data(username):
    gh_stats = {"public_repos": 6, "followers": 0, "following": 0}
    try:
        req_gh = urllib.request.Request(GITHUB_API_URL, headers={"User-Agent": headers["User-Agent"]})
        with urllib.request.urlopen(req_gh, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data:
                gh_stats["public_repos"] = data.get("public_repos", 6)
                gh_stats["followers"] = data.get("followers", 0)
                gh_stats["following"] = data.get("following", 0)
    except Exception as e:
        print(f"GitHub API fetch failed (using fallback): {e}", file=sys.stderr)
    return gh_stats

def parse_stats(data):
    # Default baseline fallbacks (Updated live profile figures)
    stats = {
        "total_solved": 444,
        "total_questions": 4055,
        "easy_solved": 275,
        "easy_total": 965,
        "medium_solved": 156,
        "medium_total": 2115,
        "hard_solved": 13,
        "hard_total": 975,
        "contest_rating": "1,626",
        "global_rank": "266,352",
        "top_percentile": "21.02%",
        "contests_attended": 42,
        "badge_count": 2,
    }

    if not data:
        return stats

    # Handles GraphQL schema
    if "allQuestionsCount" in data:
        all_q = data.get("allQuestionsCount", [])
        for q in all_q:
            diff = q.get("difficulty")
            cnt = q.get("count", 0)
            if diff == "All":
                stats["total_questions"] = cnt
            elif diff == "Easy":
                stats["easy_total"] = cnt
            elif diff == "Medium":
                stats["medium_total"] = cnt
            elif diff == "Hard":
                stats["hard_total"] = cnt

        matched = data.get("matchedUser")
        if matched:
            submit_stats = matched.get("submitStats", {}).get("acSubmissionNum", [])
            for sub in submit_stats:
                diff = sub.get("difficulty")
                cnt = sub.get("count", 0)
                if diff == "All":
                    stats["total_solved"] = cnt
                elif diff == "Easy":
                    stats["easy_solved"] = cnt
                elif diff == "Medium":
                    stats["medium_solved"] = cnt
                elif diff == "Hard":
                    stats["hard_solved"] = cnt

            badges = matched.get("badges", [])
            if badges is not None:
                stats["badge_count"] = len(badges)

            p_rank = matched.get("profile", {}).get("ranking")
            if p_rank:
                stats["global_rank"] = f"{p_rank:,}"

        contest = data.get("userContestRanking")
        if contest:
            c_rating = contest.get("rating")
            if c_rating:
                stats["contest_rating"] = f"{int(round(c_rating)):,}"
            
            top_pct = contest.get("topPercentage")
            if top_pct:
                stats["top_percentile"] = f"{top_pct:.2f}%"

            c_att = contest.get("attendedContestsCount")
            if c_att is not None:
                stats["contests_attended"] = c_att

    # Handles REST schema fallback
    elif "totalSolved" in data:
        stats["total_solved"] = data.get("totalSolved", stats["total_solved"])
        stats["easy_solved"] = data.get("easySolved", stats["easy_solved"])
        stats["medium_solved"] = data.get("mediumSolved", stats["medium_solved"])
        stats["hard_solved"] = data.get("hardSolved", stats["hard_solved"])
        if "ranking" in data:
            stats["global_rank"] = f"{data['ranking']:,}"

    return stats

def generate_svg(stats):
    easy_pct = round((stats["easy_solved"] / max(1, stats["easy_total"])) * 100, 1)
    med_pct = round((stats["medium_solved"] / max(1, stats["medium_total"])) * 100, 1)
    hard_pct = round((stats["hard_solved"] / max(1, stats["hard_total"])) * 100, 1)

    svg_content = f"""<svg fill="none" viewBox="0 0 850 300" width="850" height="300" xmlns="http://www.w3.org/2000/svg">
  <foreignObject width="100%" height="100%">
    <div xmlns="http://www.w3.org/1999/xhtml">
      <style>
        .lc-card {{
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
          background: linear-gradient(135deg, #0d1117 0%, #161b22 100%);
          border: 1px solid #30363d;
          border-radius: 16px;
          padding: 24px 36px;
          box-sizing: border-box;
          width: 850px;
          height: 300px;
          color: #c9d1d9;
          position: relative;
          overflow: hidden;
          box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
        }}

        .lc-header {{
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 20px;
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
          gap: 32px;
          height: 195px;
        }}

        .lc-col {{
          display: flex;
          flex-direction: column;
          gap: 12px;
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
          margin-bottom: 8px;
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
          padding: 14px;
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

def fetch_github_activity(username):
    import datetime
    url = f"https://github.com/users/{username}/contributions"
    req = urllib.request.Request(url, headers={"User-Agent": headers["User-Agent"]})
    
    daily_counts = {}
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8")

        td_pattern = r'data-date=\"(\d{4}-\d{2}-\d{2})\" id=\"(contribution-day-component-[^\"]+)\"'
        td_matches = re.findall(td_pattern, html)
        date_id_map = {cid: dt for dt, cid in td_matches}

        tt_pattern = r'<tool-tip[^>]*for=\"(contribution-day-component-[^\"]+)\"[^>]*>(.*?)</tool-tip>'
        tt_matches = re.findall(tt_pattern, html, re.DOTALL)

        for cid, text in tt_matches:
            dt = date_id_map.get(cid)
            if not dt:
                continue
            text_clean = text.strip()
            if "No contributions" in text_clean:
                count = 0
            else:
                m = re.search(r'(\d+)\s+contribution', text_clean)
                count = int(m.group(1)) if m else 0
            daily_counts[dt] = count
    except Exception as e:
        print(f"Error fetching GitHub contributions: {e}", file=sys.stderr)

    sorted_dates = sorted(daily_counts.keys())
    total_contribs = sum(daily_counts.values())

    # Streaks calculation
    longest_streak = 0
    longest_start = None
    longest_end = None
    temp_streak = 0
    temp_start = None

    for dt in sorted_dates:
        c = daily_counts[dt]
        if c > 0:
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

    # Current streak calculation
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    curr = 0
    curr_start = None
    curr_end = None

    for dt in reversed(sorted_dates):
        if daily_counts[dt] > 0:
            if curr == 0:
                curr_end = dt
            curr += 1
            curr_start = dt
        else:
            if dt == today_str and curr == 0:
                continue
            else:
                break

    def fmt_date(d_str):
        if not d_str:
            return ""
        dt_obj = datetime.datetime.strptime(d_str, "%Y-%m-%d")
        return dt_obj.strftime("%b %d")

    def fmt_range(s_str, e_str):
        if not s_str or not e_str:
            return ""
        s_obj = datetime.datetime.strptime(s_str, "%Y-%m-%d")
        e_obj = datetime.datetime.strptime(e_str, "%Y-%m-%d")
        if s_str == e_str:
            return s_obj.strftime("%b %d")
        elif s_obj.month == e_obj.month:
            return f"{s_obj.strftime('%b %d')} - {e_obj.strftime('%d')}"
        else:
            return f"{s_obj.strftime('%b %d')} - {e_obj.strftime('%b %d')}"

    date_range_str = f"{fmt_date(sorted_dates[0])}, {sorted_dates[0][:4]} – {fmt_date(sorted_dates[-1])}, {sorted_dates[-1][:4]}" if sorted_dates else ""
    curr_streak_dates = fmt_range(curr_start, curr_end) if curr > 0 else "Recent"
    longest_streak_dates = fmt_range(longest_start, longest_end) if longest_streak > 0 else "Recent"

    # Build Heatmap SVG Rectangles (52 weeks x 7 days)
    rects_svg = []
    if sorted_dates:
        start_dt = datetime.datetime.strptime(sorted_dates[0], "%Y-%m-%d")
        start_wday = start_dt.weekday()
        week_idx = 0
        day_idx = (start_wday + 1) % 7

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

            x_pos = week_idx * 8.2
            y_pos = day_idx * 8.2
            rects_svg.append(f'<rect x="{x_pos:.1f}" y="{y_pos:.1f}" width="6.5" height="6.5" rx="1.5" fill="{fill}" />')

            day_idx += 1
            if day_idx == 7:
                day_idx = 0
                week_idx += 1

    heatmap_svg = "".join(rects_svg)

    return {
        "total_contributions": total_contribs,
        "current_streak": curr,
        "current_streak_dates": curr_streak_dates,
        "longest_streak": longest_streak,
        "longest_streak_dates": longest_streak_dates,
        "date_range": date_range_str,
        "heatmap_svg": heatmap_svg,
    }

def generate_github_svg(act, gh_stats):
    svg_content = f"""<svg fill="none" viewBox="0 0 850 380" width="850" height="380" xmlns="http://www.w3.org/2000/svg">
  <foreignObject width="100%" height="100%">
    <div xmlns="http://www.w3.org/1999/xhtml">
      <style>
        .gh-card {{
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
          background: linear-gradient(135deg, #0d1117 0%, #161b22 100%);
          border: 1px solid #30363d;
          border-radius: 16px;
          padding: 24px 32px;
          box-sizing: border-box;
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

def update_readme_table(readme_path, stats):
    try:
        with open(readme_path, "r", encoding="utf-8") as f:
            content = f.read()

        timestamp = int(time.time())
        # Update SVG image reference timestamp
        content = re.sub(
            r'src="\./assets/leetcode_stats\.svg\?v=\d+"',
            f'src="./assets/leetcode_stats.svg?v={timestamp}"',
            content
        )
        content = re.sub(
            r'src="\./assets/github_stats\.svg\?v=\d+"',
            f'src="./assets/github_stats.svg?v={timestamp}"',
            content
        )
        if 'src="./assets/leetcode_stats.svg"' in content:
            content = content.replace(
                'src="./assets/leetcode_stats.svg"',
                f'src="./assets/leetcode_stats.svg?v={timestamp}"'
            )

        # Update LeetCode table metrics dynamically
        new_table_rows = f"""| 🏆 **Global Rank** | **{stats["global_rank"]}** | Top **{stats["top_percentile"]}** worldwide |
| 📈 **Contest Rating** | **{stats["contest_rating"]}** | **{stats["contests_attended"]}** Contests Attended |
| 💻 **Total Problems Solved** | **{stats["total_solved"]} / {stats["total_questions"]:,}** | 🟢 **{stats["easy_solved"]}** Easy \\| 🟡 **{stats["medium_solved"]}** Medium \\| 🔴 **{stats["hard_solved"]}** Hard |
| 🏅 **Badges** | **{stats["badge_count"]} Badges** | Profile: [@Sharathbcs](https://leetcode.com/u/Sharathbcs/) |"""

        table_pattern = r"(\| Metric \| Verified Current Figure \| Detail Breakdown \|[\s\S]*?\| 🏅 \*\*Badges\*\* \|[\s\S]*?\n)"
        replacement = f"| Metric | Verified Current Figure | Detail Breakdown |\n| :--- | :---: | :--- |\n{new_table_rows}\n"

        content = re.sub(table_pattern, replacement, content)

        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(content)
        print("Updated README.md table with latest LeetCode statistics.")
    except Exception as e:
        print(f"Error updating README.md: {e}", file=sys.stderr)

def main():
    print(f"Fetching LeetCode data for username: {LEETCODE_USERNAME}...")
    raw_data = fetch_leetcode_data(LEETCODE_USERNAME)
    stats = parse_stats(raw_data)
    
    print(f"Fetching GitHub user stats for username: {GITHUB_USERNAME}...")
    gh_stats = fetch_github_data(GITHUB_USERNAME)

    print(f"Fetching GitHub activity & contributions for username: {GITHUB_USERNAME}...")
    gh_activity = fetch_github_activity(GITHUB_USERNAME)

    print(f"Parsed LeetCode Statistics: {stats}")
    print(f"Parsed GitHub Stats: {gh_stats}")
    print(f"Parsed GitHub Activity: Total={gh_activity['total_contributions']}, CurrentStreak={gh_activity['current_streak']}, LongestStreak={gh_activity['longest_streak']}")

    # Generate and save LeetCode SVG
    lc_svg = generate_svg(stats)
    with open("assets/leetcode_stats.svg", "w", encoding="utf-8") as f:
        f.write(lc_svg)
    print("Saved assets/leetcode_stats.svg")

    # Generate and save GitHub SVG
    gh_svg = generate_github_svg(gh_activity, gh_stats)
    with open("assets/github_stats.svg", "w", encoding="utf-8") as f:
        f.write(gh_svg)
    print("Saved assets/github_stats.svg")

    # Update README table
    update_readme_table("README.md", stats)

if __name__ == "__main__":
    main()
