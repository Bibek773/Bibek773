import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


USERNAME = os.environ.get("GITHUB_USERNAME", "Bibek773")
TOKEN = os.environ.get("GH_TOKEN")

OUTPUT = Path("assets/contribution-graph.svg")

GRAPHQL_URL = "https://api.github.com/graphql"

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


def fetch_contributions():
    if not TOKEN:
        raise RuntimeError(
            "GH_TOKEN is missing. "
            "This is normally provided automatically by GitHub Actions."
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
            data = json.loads(response.read().decode("utf-8"))

    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"GitHub API returned HTTP {e.code}: {body}"
        )

    except URLError as e:
        raise RuntimeError(
            f"Could not connect to GitHub: {e.reason}"
        )

    if "errors" in data:
        raise RuntimeError(
            "GitHub GraphQL error:\n"
            + json.dumps(data["errors"], indent=2)
        )

    user = data.get("data", {}).get("user")

    if user is None:
        raise RuntimeError(
            f"GitHub user '{USERNAME}' was not found."
        )

    return user["contributionsCollection"]["contributionCalendar"]


def get_last_365_days(calendar):
    days = []

    for week in calendar["weeks"]:
        for day in week["contributionDays"]:
            days.append({
                "date": datetime.strptime(day["date"], "%Y-%m-%d").date(),
                "count": day["contributionCount"]
            })

    days.sort(key=lambda x: x["date"])

    if not days:
        raise RuntimeError("No contribution data returned by GitHub.")

    end_date = days[-1]["date"]
    start_date = end_date - timedelta(days=364)

    filtered = [
        day for day in days
        if start_date <= day["date"] <= end_date
    ]

    # Ensure every day exists, even if GitHub ever returns incomplete data.
    lookup = {day["date"]: day["count"] for day in filtered}

    result = []

    current = start_date

    while current <= end_date:
        result.append({
            "date": current,
            "count": lookup.get(current, 0)
        })

        current += timedelta(days=1)

    return result


def smooth_path(points):
    """
    Create a smooth cubic Bézier line through all points.
    """

    if len(points) < 2:
        return ""

    path = f"M {points[0][0]:.2f},{points[0][1]:.2f}"

    for i in range(1, len(points)):
        x0, y0 = points[i - 1]
        x1, y1 = points[i]

        dx = (x1 - x0) * 0.45

        cp1_x = x0 + dx
        cp1_y = y0

        cp2_x = x1 - dx
        cp2_y = y1

        path += (
            f" C "
            f"{cp1_x:.2f},{cp1_y:.2f} "
            f"{cp2_x:.2f},{cp2_y:.2f} "
            f"{x1:.2f},{y1:.2f}"
        )

    return path


def escape(value):
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def generate_svg(days, total_contributions):
    # ---------------------------------------------------------
    # Dimensions
    # ---------------------------------------------------------

    width = 1000
    height = 300

    left = 55
    right = 20
    top = 35
    bottom = 45

    chart_width = width - left - right
    chart_height = height - top - bottom

    # ---------------------------------------------------------
    # Scale
    # ---------------------------------------------------------

    max_count = max(day["count"] for day in days)

    if max_count == 0:
        max_count = 1

    # Round the top of the Y-axis upward.
    if max_count <= 5:
        y_max = 5
    elif max_count <= 10:
        y_max = 10
    elif max_count <= 20:
        y_max = 20
    elif max_count <= 50:
        y_max = ((max_count + 4) // 5) * 5
    else:
        y_max = ((max_count + 9) // 10) * 10

    # ---------------------------------------------------------
    # Convert data → screen coordinates
    # ---------------------------------------------------------

    points = []

    for index, day in enumerate(days):
        x = (
            left
            + (index / (len(days) - 1))
            * chart_width
        )

        y = (
            top
            + chart_height
            - (day["count"] / y_max)
            * chart_height
        )

        points.append((x, y))

    line_path = smooth_path(points)

    # ---------------------------------------------------------
    # SVG
    # ---------------------------------------------------------

    svg = []

    svg.append(
        f'''<svg xmlns="http://www.w3.org/2000/svg"
        width="{width}"
        height="{height}"
        viewBox="0 0 {width} {height}"
        role="img"
        aria-label="GitHub contribution activity graph">

        <title>
            {escape(total_contributions)} contributions in the last year
        </title>

        <style>
            .background {{
                fill: #ffffff;
            }}

            .grid {{
                stroke: #d8dee4;
                stroke-width: 1;
                opacity: 0.65;
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

                font-size: 12px;
                font-weight: 600;
                fill: #24292f;
            }}

            .line {{
                fill: none;
                stroke: #3fb950;
                stroke-width: 3;
                stroke-linecap: round;
                stroke-linejoin: round;
            }}

            .point {{
                fill: #3fb950;
                opacity: 0;
            }}

            .point:hover {{
                opacity: 1;
            }}

            .tooltip {{
                font-family:
                    -apple-system,
                    BlinkMacSystemFont,
                    "Segoe UI",
                    Helvetica,
                    Arial,
                    sans-serif;

                font-size: 10px;
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

    # ---------------------------------------------------------
    # Title
    # ---------------------------------------------------------

    svg.append(
        f'''
        <text
            class="title"
            x="{left}"
            y="18"
        >
            Contributions
        </text>
        '''
    )

    # ---------------------------------------------------------
    # Y-axis grid
    # ---------------------------------------------------------

    grid_steps = 4

    for i in range(grid_steps + 1):
        value = (y_max / grid_steps) * i

        y = (
            top
            + chart_height
            - (value / y_max) * chart_height
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
                text-anchor="end"
            >
                {int(value)}
            </text>
            '''
        )

    # ---------------------------------------------------------
    # Vertical grid lines
    # ---------------------------------------------------------

    for i in range(0, len(days), 30):
        x = (
            left
            + (i / (len(days) - 1))
            * chart_width
        )

        svg.append(
            f'''
            <line
                class="grid"
                x1="{x:.2f}"
                y1="{top}"
                x2="{x:.2f}"
                y2="{top + chart_height}"
            />
            '''
        )

    # ---------------------------------------------------------
    # Month labels
    # ---------------------------------------------------------

    previous_month = None

    for index, day in enumerate(days):
        month_key = (day["date"].year, day["date"].month)

        if month_key != previous_month:
            x = (
                left
                + (index / (len(days) - 1))
                * chart_width
            )

            label = day["date"].strftime("%b")

            svg.append(
                f'''
                <text
                    class="axis-label"
                    x="{x:.2f}"
                    y="{height - 12}"
                    text-anchor="middle"
                >
                    {label}
                </text>
                '''
            )

            previous_month = month_key

    # ---------------------------------------------------------
    # Main smooth line
    # ---------------------------------------------------------

    svg.append(
        f'''
        <path
            class="line"
            d="{line_path}"
        />
        '''
    )

    # ---------------------------------------------------------
    # Invisible interactive points
    # ---------------------------------------------------------

    point_radius = 5

    for index, day in enumerate(days):
        x, y = points[index]

        tooltip = (
            f'{day["count"]} contribution'
            f'{"s" if day["count"] != 1 else ""}'
            f' on {day["date"].strftime("%b %d, %Y")}'
        )

        svg.append(
            f'''
            <circle
                class="point"
                cx="{x:.2f}"
                cy="{y:.2f}"
                r="{point_radius}"
            >
                <title>{escape(tooltip)}</title>
            </circle>
            '''
        )

    svg.append("</svg>")

    return "\n".join(svg)


def main():
    print(f"Fetching GitHub contributions for {USERNAME}...")

    calendar = fetch_contributions()

    total = calendar["totalContributions"]

    days = get_last_365_days(calendar)

    svg = generate_svg(
        days,
        total
    )

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    OUTPUT.write_text(
        svg,
        encoding="utf-8"
    )

    print(
        f"Generated {OUTPUT}"
    )

    print(
        f"Total contributions: {total}"
    )

    print(
        f"Days plotted: {len(days)}"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
