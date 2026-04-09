import csv
import json
import os
import pathlib
import typing

import click
from slugify import slugify

from .. import schema, utils

# TODO: Complete this transformer once we have inspected real OC ENR data.
#
# The ENR system (livevoterturnout.com) typically structures contest data as:
#   {
#     "Contests": [
#       {
#         "C": "Contest name",
#         "P": "Precincts reporting string",
#         "CH": [{"N": "Candidate name", "P": "Party", "V": 1234}, ...]
#       }
#     ]
#   }
#
# Verify the actual field names against a live download before implementing.
# Key things to confirm:
#   - Contest name field (likely "C" or "Title")
#   - Candidate name, party, vote fields
#   - Precincts reporting format
#   - Whether vote totals are ints or strings


@click.command()
@click.option(
    "--election",
    default=None,
    help="Election config name from elections/ dir (e.g. 2026-june-primary)",
)
def cli(election):
    """Transform Orange County raw data into something ready to publish."""
    raw_path = utils.RAW_DATA_DIR / "orange_county" / "latest.json"
    if not raw_path.exists():
        raise FileNotFoundError(
            f"No raw data at {raw_path}. Run download first."
        )

    raw_data = json.load(open(raw_path))
    corrections = get_corrections(election)

    transformed_list = {
        "scraped_datetime": utils.now().isoformat(),
        "updated_datetime": raw_data.get("scraped_datetime"),
        "races": [],
    }

    # TODO: Replace with actual field names once schema is confirmed from live data
    for contest in raw_data.get("contests", {}).get("Contests", []):
        obj = ContestTransformer(contest, corrections)
        if not obj.include():
            continue
        transformed_list["races"].append(obj.dump())

    output_dir = utils.TRANSFORMED_DATA_DIR / "orange_county"
    timestamp_path = output_dir / f"{transformed_list['scraped_datetime']}.json"
    utils.write_json(transformed_list, timestamp_path)

    latest_path = output_dir / "latest.json"
    utils.write_json(transformed_list, latest_path)


def get_corrections(election: typing.Optional[str] = None) -> typing.Dict:
    """Open the lookup of corrections to the raw data.

    Priority: election YAML corrections_url → OC_CORRECTIONS_SHEET_URL env var → local corrections.csv
    """
    if election:
        config = utils.load_election_config(election)
        url = config["sources"].get("orange_county", {}).get("corrections_url")
        if url:
            return utils.get_corrections_from_sheet(url)
    url = os.environ.get("OC_CORRECTIONS_SHEET_URL")
    if url:
        return utils.get_corrections_from_sheet(url)
    this_dir = pathlib.Path(__file__).parent.absolute()
    correx_path = this_dir / "corrections.csv"
    correx_reader = csv.DictReader(open(correx_path))
    return {d["raw_name"]: d for d in correx_reader}


class CandidateResultTransformer(schema.BaseTransformer):
    """Map OC raw candidate data to the schema."""

    model = schema.CandidateResult

    def transform_data(self):
        """Create a new object."""
        # TODO: Confirm field names from live ENR data
        return dict(
            name=self.raw["N"].lower().title(),
            party=self.raw.get("P") or None,
            votes=int(self.raw["V"]),
            votes_percent=self.raw["votes_percent"],
            incumbent=self.raw.get("incumbent", None),
        )


class ContestTransformer(schema.BaseTransformer):
    """Map OC raw contest data to the schema."""

    model = schema.Contest

    def _get_correction(self):
        # TODO: Confirm the contest name field from live ENR data
        return self.corrections.get(self.raw.get("C", ""))

    def include(self):
        """Determine if we want to keep this record, based on our corrections."""
        correction = self._get_correction()
        if correction is None:
            return False
        return correction["include"].lower() == "yes"

    def transform_data(self):
        """Create a new object."""
        data = dict(
            name=self.correct_name(),
            slug=slugify(self.correct_name().split(":")[0].strip()),
            description=self.correct_description(),
            geography=self.correct_geography(),
            level=self.correct_level(),
            precincts_reporting=self.raw.get("P"),
            sort_order=self.correct_sort_order(),
        )

        candidate_list = list(self.raw.get("CH", []))

        # Mark incumbents
        correction = self._get_correction()
        if correction and correction.get("incumbent"):
            for c in candidate_list:
                c["incumbent"] = c["N"].upper() in correction["incumbent"].upper()

        # Set vote percentages
        vote_total = sum(int(c["V"]) for c in candidate_list)
        for c in candidate_list:
            c["votes_percent"] = (
                round(int(c["V"]) / vote_total, 4) if vote_total > 0 else 0.0
            )

        data["candidates"] = [CandidateResultTransformer(c).dump() for c in candidate_list]
        return data

    def correct_name(self):
        """Return corrected contest name from corrections lookup."""
        return self._get_correction()["clean_name"]

    def correct_description(self):
        """Return corrected contest description from corrections lookup."""
        return self._get_correction()["clean_description"]

    def correct_geography(self):
        """Return corrected geography label from corrections lookup."""
        return self._get_correction()["clean_geography"]

    def correct_level(self):
        """Return corrected contest level from corrections lookup."""
        return self._get_correction()["clean_level"]

    def correct_sort_order(self):
        """Return sort order integer from corrections lookup, or None."""
        return self._get_correction()["sort_order"] or None


if __name__ == "__main__":
    cli()
