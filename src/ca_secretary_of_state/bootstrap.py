import csv
import json
import sys

import click
from rich import print

from .. import utils


@click.command()
def cli():
    """Generate a corrections.csv template from downloaded CA SOS raw data.

    Run download first, then pipe the output to corrections.csv:

        pipenv run python -m src.ca_secretary_of_state.bootstrap > src/ca_secretary_of_state/corrections.csv
    """
    raw_dir = utils.RAW_DATA_DIR / "ca_secretary_of_state"
    if not raw_dir.exists():
        print("[red]No raw data found. Run download first.[/red]")
        sys.exit(1)

    latest_files = [f for f in raw_dir.glob("**/latest.json")]
    if not latest_files:
        print("[red]No latest.json files found. Run download first.[/red]")
        sys.exit(1)

    race_titles = set()
    for file_path in latest_files:
        raw_data = json.load(open(file_path))
        slug = file_path.parent.stem

        if slug == "courts-of-appeal":
            for division in raw_data.get("races", []):
                for race in division.get("courts-of-appeal", []):
                    key = division["raceTitle"].split("-")[0].strip()
                    race_titles.add(f"{key}: {race['Name']}")
        elif "races" in raw_data:
            for race in raw_data["races"]:
                key = race.get("raceTitle", "").split("-")[0].strip()
                if key:
                    race_titles.add(key)
        elif slug == "supreme-court":
            for race in raw_data.get("supreme-court", []):
                race_titles.add(f"Retain Supreme Court Justice {race['Name']}")
        elif slug == "ballot-measures":
            for race in raw_data.get("ballot-measures", []):
                race_titles.add(f"Proposition {race['Number']}: {race['Name']}")
        else:
            key = raw_data.get("raceTitle", "").split("-")[0].strip()
            if key:
                race_titles.add(key)

    race_titles = sorted(race_titles)

    fieldnames = [
        "raw_name",
        "include",
        "clean_geography",
        "clean_level",
        "clean_name",
        "clean_description",
        "sort_order",
        "incumbent",
        "incumbent_current_district",
    ]
    writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
    writer.writeheader()
    for title in race_titles:
        writer.writerow({"raw_name": title, "include": "No"})

    print(
        f"[green]✅ {len(race_titles)} contests written.[/green] "
        "Set include=Yes and fill in clean_* fields for races you want to publish.",
        file=sys.stderr,
    )


if __name__ == "__main__":
    cli()
