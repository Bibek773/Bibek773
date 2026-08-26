import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


# ============================================================
# Configuration
# ============================================================

USERNAME = os.environ.get("GITHUB_USERNAME", "Bibek773")
TOKEN = os.environ.get("GH_TOKEN")

OUTPUT = Path("assets/contribution-graph.svg")

GRAPHQL_URL = "https://api.github.com/graphql"

DAYS_TO_SHOW = 31


# ============================================================
# GitHub GraphQL Query
# ============================================================

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
  }
}
"""


# ============================================================
# Fetch contribution data
# ============================================================

def fetch_contributions():
    if not TOKEN:
        raise RuntimeError(
            "GH_TOKEN is missing. "
            "When running through GitHub Actions, this is provided "
            "automatically."
        )

    payload = json.dumps({
        "query": QUERY,
        "variables": {
            "login": USERNAME
        }
    }).encode("utf-8")

    request = Request(
        GRAPHQL_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "GitHub-Contribution-Graph"
        },
        method="POST"
    )

    try:
        with urlopen(request, timeout=30) as response:
            data = json.loads(
                response.read().decode("utf-8")
            )

    except HTTPError as error:
        body = error.read().decode(
            "utf-8",
            errors="replace"
        )

        raise RuntimeError(
            f"GitHub API returned HTTP {error.code}: {body}"
        )

    except URLError as error:
        raise RuntimeError(
            f"Could not connect to GitHub: {error.reason}"
        )

    if "errors" in data:
        raise RuntimeError(
            "GitHub GraphQL error:\n"
            + json.dumps(
                data["errors"],
                indent=2
            )
        )

    user = data.get("data", {}).get("user")

    if user is None:
        raise RuntimeError(
            f"GitHub user '{USERNAME}' was not found."
        )

    return (
        user["contributionsCollection"]
        ["contributionCalendar"]
    )


# ============================================================
# Get last 31 days
# ============================================================

def get_last_31_days(calendar):
    all_days = []

    for week in calendar["weeks"]:
        for day in week["contributionDays"]:

            all_days.append({
                "date": datetime.strptime(
                    day["date"],
                    "%Y-%m-%d"
                ).date(),

                "count": day["contributionCount"]
            })

    all_days.sort(
        key=lambda item: item["date"]
    )

    if not all_days:
        raise RuntimeError(
            "GitHub returned no contribution data."
        )

    # GitHub's latest available contribution date
    end_date = all_days[-1]["date"]

    start_date = (
        end_date
        - timedelta(days=DAYS_TO_SHOW - 1)
    )

    lookup = {
        item["date"]: item["count"]
        for item in all_days
    }

    result = []

    current = start_date

    while current <= end_date:

        result.append({
            "date": current,
            "count": lookup.get(
                current,
                0
            )
        })

        current += timedelta(days=1)

    return result


# ============================================================
# XML escaping
# ============================================================

def escape(value):
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


# ============================================================
# Generate SVG bar graph
# ============================================================

def generate_svg(days):
    # --------------------------------------------------------
    # Canvas
    # --------------------------------------------------------

    width = 1000
    height = 320

    left = 55
    right = 20
    top = 40
    bottom = 55

    chart_width = (
        width
        - left
        - right
    )

    chart_height = (
        height
        - top
        - bottom
    )

    # --------------------------------------------------------
    # Maximum contribution count
    # --------------------------------------------------------

    max_count = max(
        day["count"]
        for day in days
    )

    if max_count == 0:
        max_count = 1

    # Make the Y-axis cleaner
    if max_count <= 5:
        y_max = 5

    elif max_count <= 10:
        y_max = 10

    elif max_count <= 20:
        y_max = 20

    elif max_count <= 50:
        y_max = (
            (max_count + 4) // 5
        ) * 5

    else:
        y_max = (
            (max_count + 9) // 10
        ) * 10

    # --------------------------------------------------------
    # Bar dimensions
    # --------------------------------------------------------

    bar_gap = 8

    bar_width = (
        chart_width
        / len(days)
    ) - bar_gap

    # --------------------------------------------------------
    # SVG start
    # --------------------------------------------------------

    svg = []

    svg.append(
        f'''<svg
        xmlns="http://www.w3.org/2000/svg"
        width="{width}"
        height="{height}"
        viewBox="0 0 {width} {height}"
        role="img"
        aria-label="GitHub contribution activity for the last 31 days"
        preserveAspectRatio="xMidYMid meet">

        <title>
            GitHub contribution activity for the last 31 days
        </title>

        <style>

            .background {{
                fill: #ffffff;
            }}

            .grid {{
                stroke: #d8dee4;
                stroke-width: 1;
                opacity: 0.7;
            }}

            .axis-label {{
                font-family:
                    -apple-system,
                    BlinkMacSystemFont,
                    "Segoe UI",
                    Helvetica,
                    Arial,
                    sans-serif;

                font-size: 11px;
                fill: #656d76;
            }}

            .title {{
                font-family:
                    -apple-system,
                    BlinkMacSystemFont,
                    "Segoe UI",
                    Helvetica,
                    Arial,
                    sans-serif;

                font-size: 13px;
                font-weight: 600;
                fill: #24292f;
            }}

            .bar {{
                fill: #3fb950;
                rx: 3;
                ry: 3;
            }}

            .bar:hover {{
                fill: #2da44e;
            }}

        </style>

        <rect
            class="background"
            x="0"
            y="0"
            width="{width}"
            height="{height}"
        />
        '''
    )

    # --------------------------------------------------------
    # Title
    # --------------------------------------------------------

    svg.append(
        f'''
        <text
            class="title"
            x="{left}"
            y="20">
            Contributions — Last 31 Days
        </text>
        '''
    )

    # --------------------------------------------------------
    # Y-axis grid
    # --------------------------------------------------------

    grid_steps = 4

    for i in range(grid_steps + 1):

        value = (
            y_max
            / grid_steps
            * i
        )

        y = (
            top
            + chart_height
            - (
                value
                / y_max
            )
            * chart_height
        )

        svg.append(
            f'''
            <line
                class="grid"
                x1="{left}"
                y1="{y:.2f}"
                x2="{width - right}"
                y2="{y:.2f}"
            />

            <text
                class="axis-label"
                x="{left - 10}"
                y="{y + 4:.2f}"
                text-anchor="end">
                {int(value)}
            </text>
            '''
        )

    # --------------------------------------------------------
    # Bars
    # --------------------------------------------------------

    for index, day in enumerate(days):

        count = day["count"]

        x = (
            left
            + index
            * (
                chart_width
                / len(days)
            )
            + bar_gap / 2
        )

        bar_height = (
            count
            / y_max
            * chart_height
        )

        y = (
            top
            + chart_height
            - bar_height
        )

        # Make zero-contribution days visible
        if count == 0:
            bar_height = 2

            y = (
                top
                + chart_height
                - 2
            )

        date_text = day["date"].strftime(
            "%b %d, %Y"
        )

        contribution_text = (
            f"{count} contribution"
            f"{'s' if count != 1 else ''}"
        )

        tooltip = (
            f"{contribution_text} "
            f"on {date_text}"
        )

        svg.append(
            f'''
            <rect
                class="bar"
                x="{x:.2f}"
                y="{y:.2f}"
                width="{bar_width:.2f}"
                height="{bar_height:.2f}">

                <title>
                    {escape(tooltip)}
                </title>

            </rect>
            '''
        )

    # --------------------------------------------------------
    # Date labels
    # --------------------------------------------------------

    # Show every 5th day + final day
    label_indices = set(
        range(0, len(days), 5)
    )

    label_indices.add(
        len(days) - 1
    )

    for index in sorted(label_indices):

        day = days[index]

        x = (
            left
            + index
            * (
                chart_width
                / len(days)
            )
            + (
                chart_width
                / len(days)
            ) / 2
        )

        label = day["date"].strftime(
            "%b %d"
        )

        svg.append(
            f'''
            <text
                class="axis-label"
                x="{x:.2f}"
                y="{height - 18}"
                text-anchor="middle">
                {escape(label)}
            </text>
            '''
        )

    # --------------------------------------------------------
    # Close SVG
    # --------------------------------------------------------

    svg.append("</svg>")

    return "\n".join(svg)


# ============================================================
# Main
# ============================================================

def main():

    print(
        f"Fetching GitHub contributions "
        f"for {USERNAME}..."
    )

    calendar = fetch_contributions()

    days = get_last_31_days(
        calendar
    )

    svg = generate_svg(
        days
    )

    # Create assets directory automatically
    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    # Create SVG automatically
    OUTPUT.write_text(
        svg,
        encoding="utf-8"
    )

    total = sum(
        day["count"]
        for day in days
    )

    print(
        f"Generated: {OUTPUT}"
    )

    print(
        f"Days: {len(days)}"
    )

    print(
        f"Contributions in last 31 days: {total}"
    )


if __name__ == "__main__":

    try:
        main()

    except Exception as error:

        print(
            f"ERROR: {error}",
            file=sys.stderr
        )

        sys.exit(1)