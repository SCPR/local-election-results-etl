import click

from .. import utils


@click.command()
@click.option(
    "--election",
    default=None,
    help="Election config name from elections/ dir (e.g. 2026-june-primary)",
)
@click.option(
    "--election-id",
    "election_id",
    default=None,
    type=int,
    help="Override the LAC election ID directly",
)
def cli(election, election_id):
    """Download JSON data posted by the L.A. County Registrar/Recorder."""
    if election_id is None:
        if election:
            config = utils.load_election_config(election)
            election_id = config["sources"]["los_angeles_county"]["election_id"]
        else:
            raise click.UsageError(
                "Provide --election <name> or --election-id <id>"
            )

    # Get the latest data
    url = f"https://results.lavote.gov/electionresults/json?electionid={election_id}"
    data = utils.request_json(url)

    # Write out a timestamped file
    timestamp_path = (
        utils.RAW_DATA_DIR / "los_angeles_county" / f"{utils.now().isoformat()}.json"
    )
    utils.write_json(data, timestamp_path)

    # Overwrite the latest file
    latest_path = utils.RAW_DATA_DIR / "los_angeles_county" / "latest.json"
    utils.write_json(data, latest_path)


if __name__ == "__main__":
    cli()
