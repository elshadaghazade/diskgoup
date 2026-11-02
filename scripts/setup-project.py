#!/usr/bin/env python3
"""Create the DiskGOup project board — the Kanban board over the issues.

The board is a view over the issues, not a second place to write things down:
an issue that is in *In progress* is an issue whose label says so. The columns
are the workflow:

    Backlog → Planned → In progress → In review → Done

    python3 scripts/setup-project.py

The GitHub CLI needs the `project` scope for this. If it is missing, the
script says so and prints the command that grants it:

    gh auth refresh -s project,read:project

Only the standard library is needed.
"""

from __future__ import annotations

import json
import subprocess
import sys

OWNER = "elshadaghazade"
TITLE = "DiskGOup"

# The columns, in the order they are worked through. The first three reuse the
# options the new project already has; the last two are added.
COLUMNS = ["Backlog", "Planned", "In progress", "In review", "Done"]

COLORS = {
    "Backlog": "GRAY",
    "Planned": "BLUE",
    "In progress": "YELLOW",
    "In review": "PURPLE",
    "Done": "GREEN",
}


def run(args: list[str], *, stdin: str | None = None) -> str:
    result = subprocess.run(
        args,
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"✗ {' '.join(args[:3])} failed:\n{result.stderr.strip()}")
    return result.stdout


def graphql(query: str, variables: dict[str, object]) -> dict:
    payload = json.dumps({"query": query, "variables": variables})
    raw = run(
        ["gh", "api", "graphql", "--input", "-"],
        stdin=payload,
    )
    data = json.loads(raw)
    if "errors" in data:
        raise SystemExit(
            "✗ the GitHub API refused the request:\n"
            + "\n".join(f"  {e.get('message')}" for e in data["errors"])
        )
    return data["data"]


def ensure_scope() -> None:
    status = run(["gh", "auth", "status"])
    if "project" in status and "missing required scopes" not in status:
        return
    print(
        "✗ the GitHub CLI token is missing the 'project' scope.\n"
        "  Grant it with:\n\n"
        "      gh auth refresh -s project,read:project\n"
    )
    raise SystemExit(1)


def find_or_create() -> tuple[str, str]:
    """The project id and its URL."""
    projects = json.loads(run(["gh", "project", "list", "--owner", OWNER, "--format", "json"]))
    for project in projects.get("projects", []):
        if project.get("title") == TITLE:
            print(f"→ the project {TITLE} already exists")
            return project["id"], project["url"]

    created = json.loads(
        run(
            [
                "gh",
                "project",
                "create",
                "--owner",
                OWNER,
                "--title",
                TITLE,
                "--format",
                "json",
            ]
        )
    )
    print(f"✓ created the project {TITLE}")
    return created["id"], created["url"]


def status_field(project_id: str) -> tuple[str, list[dict]]:
    data = graphql(
        """
        query($project: ID!, $owner: String!) {
          organization(login: $owner) { projectV2(id: $project) {
            fields(first: 50) { nodes {
              ... on ProjectV2SingleSelectField { id name options { id name } }
            } }
          } }
        }
        """,
        {"project": project_id, "owner": OWNER},
    )
    fields = data["organization"]["projectV2"]["fields"]["nodes"]
    for field in fields:
        if field.get("name") == "Status":
            return field["id"], field.get("options", [])
    raise SystemExit("✗ the project has no Status field")


def set_columns(project_id: str, field_id: str, options: list[dict]) -> None:
    """Rename the existing options and add the missing ones."""
    single = []
    for index, column in enumerate(COLUMNS):
        option = {"name": column, "color": COLORS[column]}
        if index < len(options):
            option["id"] = options[index]["id"]
        single.append(option)

    graphql(
        """
        mutation($project: ID!, $field: ID!, $options: [ProjectV2SingleSelectFieldOptionInput!]!) {
          updateProjectV2Field(input: {
            projectId: $project,
            fieldId: $field,
            singleSelectOptions: $options
          }) { projectV2Field { ... on ProjectV2SingleSelectField { name options { name } } } }
        }
        """,
        {"project": project_id, "field": field_id, "options": single},
    )


def main() -> int:
    # The console on Windows is cp1252 and cannot hold a "✓".
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    ensure_scope()
    project_id, url = find_or_create()
    field_id, options = status_field(project_id)
    set_columns(project_id, field_id, options)
    print(f"✓ the columns are now: {' → '.join(COLUMNS)}")
    print(f"✓ {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
