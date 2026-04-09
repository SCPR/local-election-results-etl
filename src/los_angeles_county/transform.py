import csv
import json
import os
import pathlib
import typing

import click
from slugify import slugify

from .. import schema, utils


@click.command()
@click.option(
    "--election",
    default=None,
    help="Election config name from elections/ dir (e.g. 2026-june-primary)",
)
def cli(election):
    """Transform the raw data into something ready to publish."""
    # Read in the raw file
    raw_path = utils.RAW_DATA_DIR / "los_angeles_county" / "latest.json"
    raw_data = json.load(open(raw_path))

    corrections = get_corrections(election)

    # Flatten the list
    contest_list = []
    for contestgroup in raw_data["Election"]["ContestGroups"]:
        for contest in contestgroup["Contests"]:
            contest_list.append(contest)

    # Load it up
    transformed_list = {
        "scraped_datetime": utils.now().isoformat(),
        "updated_datetime": raw_data["Timestamp"],
        "races": [],
    }
    for contest in contest_list:
        # Tidy
        obj = ContestTransformer(contest, corrections)

        # Exclude records we don't want
        if not obj.include():
            continue

        # Add to our master list
        transformed_list["races"].append(obj.dump())

    # Write out a timestamped file
    output_dir = utils.TRANSFORMED_DATA_DIR / "los_angeles_county"
    timestamp_path = output_dir / f"{transformed_list['scraped_datetime']}.json"
    utils.write_json(transformed_list, timestamp_path)

    # Overwrite the latest file
    latest_path = output_dir / "latest.json"
    utils.write_json(transformed_list, latest_path)


def get_corrections(election: typing.Optional[str] = None) -> typing.Dict:
    """Open the lookup of corrections to the raw data.

    Priority: election YAML corrections_url → LAC_CORRECTIONS_SHEET_URL env var → local corrections.csv
    """
    # 1. Election config URL
    if election:
        config = utils.load_election_config(election)
        url = config["sources"]["los_angeles_county"].get("corrections_url")
        if url:
            return utils.get_corrections_from_sheet(url)
    # 2. Env var (active election override)
    url = os.environ.get("LAC_CORRECTIONS_SHEET_URL")
    if url:
        return utils.get_corrections_from_sheet(url)
    # 3. Local CSV fallback (for tests and offline dev)
    this_dir = pathlib.Path(__file__).parent.absolute()
    correx_path = this_dir / "corrections.csv"
    correx_reader = csv.DictReader(open(correx_path))
    return {d["raw_name"]: d for d in correx_reader}


class CandidateResultTransformer(schema.BaseTransformer):
    """Map our raw candidate results to the schema."""

    model = schema.CandidateResult

    def transform_data(self):
        """Create a new object."""
        return dict(
            name=self.clean_name(self.raw["Name"]),
            party=self.raw["Party"],
            votes=self.raw["Votes"],
            votes_percent=self.raw["votes_percent"],
            incumbent=self.raw.get("incumbent", False),
        )

    def clean_name(self, name):
        """Clean name."""
        return name.lower().title().replace("Tim Mcosker", "Tim McOsker")


class ContestTransformer(schema.BaseTransformer):
    """Map our raw contest data to the schema."""

    model = schema.Contest

    def transform_data(self):
        """Create a new object."""
        # Start off a data dictionary
        data = dict(
            name=self.correct_name(),
            slug=self.get_slug(),
            description=self.correct_description(),
            geography=self.correct_geography(),
            level=self.correct_level(),
            precincts_reporting=None,
            sort_order=self.correct_sort_order(),
        )

        # Mark incumbents
        candidate_list = [c for c in self.correct_incumbent(self.raw["Candidates"])]

        # Set vote percentages
        vote_total = sum(c["Votes"] for c in candidate_list)
        for c in candidate_list:
            if vote_total > 0:
                c["votes_percent"] = round(c["Votes"] / vote_total, 4)
            else:
                c["votes_percent"] = 0.0

        # Validate candidate objects
        candidate_list = [CandidateResultTransformer(c).dump() for c in candidate_list]

        # Add to the data dictionary
        data["candidates"] = candidate_list

        # Return the transformed data
        return data

    def _get_correction(self):
        return self.corrections.get(self.raw["Title"])

    def include(self):
        """Determine if we want to keep this record, based on our corrections."""
        correction = self._get_correction()
        if correction is None:
            return False
        return correction["include"].lower() == "yes"

    def get_slug(self):
        """Get a unique slug."""
        slug_name = self.correct_name()
        if "court" not in self.correct_geography().lower():
            slug_name = slug_name.split(":")[0].strip()
        return slugify(slug_name)

    def correct_name(self):
        """Correct the name field."""
        return self._get_correction()["clean_name"]

    def correct_description(self):
        """Correct the description field."""
        return self._get_correction()["clean_description"]

    def correct_geography(self):
        """Correct the geography field."""
        return self._get_correction()["clean_geography"]

    def correct_level(self):
        """Correct the level field."""
        return self._get_correction()["clean_level"]

    def correct_sort_order(self):
        """Correct the sort_order field."""
        return self._get_correction()["sort_order"] or None

    def correct_incumbent(
        self, candidate_list: typing.List[typing.Dict]
    ) -> typing.List[typing.Dict]:
        """Correct the incumbents field."""
        # Correct any incumbent candidates
        correction = self._get_correction()
        if correction and correction["incumbent"] and self.include():
            for c in candidate_list:
                c["incumbent"] = c["Name"].upper() in correction["incumbent"].upper()
            assert len([c for c in candidate_list if c["incumbent"]]) > 0
        return candidate_list


if __name__ == "__main__":
    cli()
