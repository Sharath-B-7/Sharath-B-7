import json
import re
import sys
import time
import urllib.request

LEETCODE_USERNAME = "Sharathbcs"
GRAPHQL_URL = "https://leetcode.com/graphql"

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
    userCalendar {
      streak
      totalActiveDays
      submissionCalendar
    }
    languageProblemCount {
      languageName
      problemsSolved
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
    payload = json.dumps({
        "query": graphql_query,
        "variables": {"username": username}
    }).encode("utf-8")
    
    req = urllib.request.Request(GRAPHQL_URL, data=payload, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            return res.get("data", {})
    except Exception as e:
        print(f"Error fetching data from LeetCode GraphQL: {e}", file=sys.stderr)
        return None

def parse_stats(data):
    # Default baseline fallbacks
    stats = {
        "total_solved": 432,
        "total_questions": 4047,
        "easy_solved": 270,
        "easy_total": 963,
        "medium_solved": 149,
        "medium_total": 2111,
        "hard_solved": 13,
        "hard_total": 973,
        "contest_rating": "1,617",
        "global_rank": "279,851",
        "top_percentile": "22.12%",
        "contests_attended": 41,
        "badge_count": 2,
        "max_streak": 55,
        "active_days": 214,
        "submissions_year": 812,
        "cpp_solved": 269,
        "py3_solved": 169,
        "py_solved": 66,
    }

    if not data:
        return stats

    # Parse Question Counts
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

    # Parse Matched User Stats
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

        # Badges
        badges = matched.get("badges", [])
        if badges is not None:
            stats["badge_count"] = len(badges)

        # Calendar
        calendar = matched.get("userCalendar", {})
        if calendar:
            stats["max_streak"] = calendar.get("streak", stats["max_streak"])
            stats["active_days"] = calendar.get("totalActiveDays", stats["active_days"])
            sub_cal_str = calendar.get("submissionCalendar", "{}")
            try:
                sub_cal = json.loads(sub_cal_str)
                total_subs = sum(sub_cal.values())
                if total_subs > 0:
                    stats["submissions_year"] = total_subs
            except Exception:
                pass

        # Languages
        lang_counts = matched.get("languageProblemCount", [])
        for lang in lang_counts:
            lname = lang.get("languageName")
            lsol = lang.get("problemsSolved", 0)
            if lname == "cpp" or lname == "C++":
                stats["cpp_solved"] = lsol
            elif lname == "python3" or lname == "Python3":
                stats["py3_solved"] = lsol
            elif lname == "python" or lname == "Python":
                stats["py_solved"] = lsol

    # Parse Contest Info
    contest = data.get("userContestRanking")
    if contest:
        c_rating = contest.get("rating")
        if c_rating:
            stats["contest_rating"] = f"{int(round(c_rating)):,}"
        
        g_rank = contest.get("globalRanking")
        if g_rank:
            stats["global_rank"] = f"{g_rank:,}"
            
        top_pct = contest.get("topPercentage")
        if top_pct:
            stats["top_percentile"] = f"{top_pct:.2f}%"

        c_att = contest.get("attendedContestsCount")
        if c_att is not None:
            stats["contests_attended"] = c_att

    return stats

def generate_svg(stats):
    easy_pct = round((stats["easy_solved"] / max(1, stats["easy_total"])) * 100, 1)
    med_pct = round((stats["medium_solved"] / max(1, stats["medium_total"])) * 100, 1)
    hard_pct = round((stats["hard_solved"] / max(1, stats["hard_total"])) * 100, 1)

    svg_content = f"""<svg fill="none" viewBox="0 0 850 340" width="850" height="340" xmlns="http://www.w3.org/2000/svg">
  <foreignObject width="100%" height="100%">
    <div xmlns="http://www.w3.org/1999/xhtml">
      <style>
        .lc-card {{
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
          background: linear-gradient(135deg, #0d1117 0%, #161b22 100%);
          border: 1px solid #30363d;
          border-radius: 16px;
          padding: 24px 32px;
          box-sizing: border-box;
          width: 850px;
          height: 340px;
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
          grid-template-columns: 1.2fr 1fr 1.1fr;
          gap: 24px;
          height: 230px;
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
          padding: 14px 16px;
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
          padding: 16px;
        }}

        .total-num {{
          font-size: 36px;
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
          padding: 6px 0;
          border-bottom: 1px dashed #21262d;
        }}

        .metric-row:last-child {{
          border-bottom: none;
        }}

        .metric-label {{ color: #8b949e; }}
        .metric-val {{ color: #f0f6fc; font-weight: 600; font-family: 'Fira Code', monospace; }}

        .lang-tag {{
          font-size: 12px;
          display: flex;
          justify-content: space-between;
          margin-bottom: 6px;
        }}

        .lang-name {{ color: #c9d1d9; font-weight: 500; }}
        .lang-count {{ color: #38bdf8; font-weight: 600; font-family: 'Fira Code', monospace; }}
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

            <div class="stat-box" style="flex: 1;">
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
                <span class="metric-val">{stats["contests_attended"]}</span>
              </div>
              <div class="metric-row">
                <span class="metric-label">🏅 Badges</span>
                <span class="metric-val">{stats["badge_count"]} Badges</span>
              </div>
            </div>
          </div>

          <!-- Col 3: Streak & Languages -->
          <div class="lc-col">
            <div class="stat-box">
              <div class="metric-row">
                <span class="metric-label">🔥 Max Streak</span>
                <span class="metric-val" style="color: #ff5f56;">{stats["max_streak"]} Days</span>
              </div>
              <div class="metric-row">
                <span class="metric-label">📅 Active Days</span>
                <span class="metric-val">{stats["active_days"]} Days</span>
              </div>
              <div class="metric-row">
                <span class="metric-label">📊 Past Year</span>
                <span class="metric-val">{stats["submissions_year"]} Subs</span>
              </div>
            </div>

            <div class="stat-box" style="flex: 1;">
              <div style="font-size: 12px; font-weight: 700; color: #8b949e; text-transform: uppercase; margin-bottom: 8px; letter-spacing: 0.5px;">
                Languages Used
              </div>
              <div class="lang-tag">
                <span class="lang-name">C++</span>
                <span class="lang-count">{stats["cpp_solved"]} solved</span>
              </div>
              <div class="lang-tag">
                <span class="lang-name">Python3</span>
                <span class="lang-count">{stats["py3_solved"]} solved</span>
              </div>
              <div class="lang-tag">
                <span class="lang-name">Python</span>
                <span class="lang-count">{stats["py_solved"]} solved</span>
              </div>
            </div>
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
        if 'src="./assets/leetcode_stats.svg"' in content:
            content = content.replace(
                'src="./assets/leetcode_stats.svg"',
                f'src="./assets/leetcode_stats.svg?v={timestamp}"'
            )

        # Update LeetCode table metrics dynamically
        new_table_rows = f"""| 🏆 **Global Rank** | **{stats["global_rank"]}** | Top **{stats["top_percentile"]}** worldwide |
| 📈 **Contest Rating** | **{stats["contest_rating"]}** | **{stats["contests_attended"]}** Contests Attended |
| 💻 **Total Problems Solved** | **{stats["total_solved"]} / {stats["total_questions"]:,}** | 🟢 **{stats["easy_solved"]}** Easy \\| 🟡 **{stats["medium_solved"]}** Medium \\| 🔴 **{stats["hard_solved"]}** Hard |
| 🔥 **Maximum Streak** | **{stats["max_streak"]} Days** | **{stats["active_days"]}** Total Active Days \\| **{stats["submissions_year"]}** Past Year Submissions |
| 💻 **Languages Used** | **C++ & Python** | **{stats["cpp_solved"]}** C++ \\| **{stats["py3_solved"]}** Python3 \\| **{stats["py_solved"]}** Python |
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
    
    print(f"Parsed LeetCode Statistics: {stats}")

    # Generate and save SVG
    svg_content = generate_svg(stats)
    with open("assets/leetcode_stats.svg", "w", encoding="utf-8") as f:
        f.write(svg_content)
    print("Saved assets/leetcode_stats.svg")

    # Update README table
    update_readme_table("README.md", stats)

if __name__ == "__main__":
    main()
