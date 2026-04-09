import csv
import json
import sys

import click
from rich import print

from .. import utils


@click.command()
def cli():
    """Generate a corrections.csv template from downloaded LAC raw data.

    Run download first, then pipe the output to corrections.csv:

        pipenv run python -m src.los_angeles_county.bootstrap > src/los_angeles_county/corrections.csv
    """
    raw_path = utils.RAW_DATA_DIR / "los_angeles_county" / "latest.json"
    if not raw_path.exists():
        print("[red]No raw data found. Run download first.[/red]")
        sys.exit(1)

    raw_data = json.load(open(raw_path))

    contest_names = []
    for group in raw_data["Election"]["ContestGroups"]:
        for contest in group["Contests"]:
            contest_names.append(contest["Title"])

    contest_names = sorted(set(contest_names))

    fieldnames = [
        "raw_name",
        "pdf_name",
        "include",
        "clean_geography",
        "clean_level",
        "clean_name",
        "clean_description",
        "sort_order",
        "incumbent",
    ]
    writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
    writer.writeheader()
    for name in contest_names:
        writer.writerow({"raw_name": name, "pdf_name": name, "include": "No"})

    print(
        f"[green]✅ {len(contest_names)} contests written.[/green] "
        "Set include=Yes and fill in clean_* fields for races you want to publish.",
        file=sys.stderr,
    )


if __name__ == "__main__":
    cli()
