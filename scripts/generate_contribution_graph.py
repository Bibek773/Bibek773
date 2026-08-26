import json
import os
import sys
from datetime import datetime
from pathlib import Path

import requests


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
        colors
        weeks {
          contributionDays {
            date
            contributionCount
            color
            weekday
          }
        }
      }
    }
  }
}
"""


def fetch_contributions():
    if not TOKEN:
        raise RuntimeError("GH_TOKEN environment variable is missing")

    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    }

    response = requests.post(
        GRAPHQL_URL,
        headers=headers,
        json={
            "query": QUERY,
            "variables": {
                "login": USERNAME
            },
        },
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    if "errors" in data:
        raise RuntimeError(
            "GitHub GraphQL error:\n"
            + json.dumps(data["errors"], indent=2)
        )

    user = data["data"]["user"]

    if user is None:
        raise RuntimeError(f"GitHub user '{USERNAME}' was not found")

    return user["contributionsCollection"]["contributionCalendar"]


def escape(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def generate_svg(calendar):
    weeks = calendar["weeks"]
    total = calendar["totalContributions"]

    # GitHub-style dimensions
    cell_size = 12
    cell_gap = 3
    step = cell_size + cell_gap

    left = 30
    top = 32

    width = left + len(weeks) * step + 10
    height = top + 7 * step + 30

    parts = []

    parts.append(
        f'''<svg xmlns="http://www.w3.org/2000/svg"
        width="{width}"
        height="{height}"
        viewBox="0 0 {width} {height}">
        <title>{escape(total)} contributions in the last year</title>

        <style>
            .label {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
                             Helvetica, Arial, sans-serif;
                font-size: 10px;
                fill: #656d76;
            }}

            .day {{
                rx: 2;
                ry: 2;
                shape-rendering: geometricPrecision;
            }}
        </style>
        '''
    )

    # Month labels
    month_positions = {}

    for week_index, week in enumerate(weeks):
        for day in week["contributionDays"]:
            date = datetime.strptime(day["date"], "%Y-%m-%d")

            # First appearance of a month
            key = (date.year, date.month)

            if key not in month_positions:
                month_positions[key] = week_index

    for (year, month), week_index in month_positions.items():
        date = datetime(year, month, 1)

        month_name = date.strftime("%b")

        x = left + week_index * step

        parts.append(
            f'<text class="label" x="{x}" y="15">'
            f'{escape(month_name)}</text>'
        )

    # Day labels
    day_labels = {
        1: "Mon",
        3: "Wed",
        5: "Fri",
    }

    for weekday, label in day_labels.items():
        y = top + weekday * step + 9

        parts.append(
            f'<text class="label" x="0" y="{y}">'
            f'{label}</text>'
        )

    # Contribution squares
    for week_index, week in enumerate(weeks):
        for day in week["contributionDays"]:
            weekday = day["weekday"]

            x = left + week_index * step
            y = top + weekday * step

            count = day["contributionCount"]
            color = day["color"]

            tooltip = (
                f'{count} contribution'
                f'{"s" if count != 1 else ""} on {day["date"]}'
            )

            parts.append(
                f'<rect class="day" '
                f'x="{x}" '
                f'y="{y}" '
                f'width="{cell_size}" '
                f'height="{cell_size}" '
                f'fill="{escape(color)}">'
                f'<title>{escape(tooltip)}</title>'
                f'</rect>'
            )

    # Total contributions
    parts.append(
        f'<text class="label" x="{left}" y="{height - 5}">'
        f'{total} contributions in the last year'
        f'</text>'
    )

    parts.append("</svg>")

    return "\n".join(parts)


def main():
    calendar = fetch_contributions()

    svg = generate_svg(calendar)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(svg, encoding="utf-8")

    print(
        f"Generated {OUTPUT} "
        f"({calendar['totalContributions']} contributions)"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)