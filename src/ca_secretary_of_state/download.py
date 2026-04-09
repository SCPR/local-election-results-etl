import click

from .. import utils

DEFAULT_SLUGS = [
    "governor",
    "lieutenant-governor",
    "secretary-of-state",
    "controller",
    "treasurer",
    "attorney-general",
    "insurance-commissioner",
    "superintendent-of-public-instruction",
    "us-senate",
    "us-senate-unexpired-term",
    "supreme-court",
    "ballot-measures",
    "board-of-equalization/district/all",
    "us-rep/district/all",
    "state-senate/district/all",
    "state-assembly/district/all",
    "courts-of-appeal/district/all",
]


@click.command()
@click.option(
    "--election",
    default=None,
    help="Election config name from elections/ dir (e.g. 2026-june-primary)",
)
def cli(election):
    """Download JSON data posted by the California Secretary of State."""
    if election:
        config = utils.load_election_config(election)
        source_config = config["sources"]["ca_secretary_of_state"]
        if "api_endpoints_url" in source_config:
            slug_list = utils.get_ca_sos_slugs_from_endpoints(
                source_config["api_endpoints_url"]
            )
        else:
            slug_list = source_config.get("slugs", DEFAULT_SLUGS)
    else:
        slug_list = DEFAULT_SLUGS

    # Get the latest data
    for slug in slug_list:
        url = f"https://api.sos.ca.gov/returns/{slug}"
        data = utils.request_json(url)
        now = utils.now().isoformat()
        if isinstance(data, list):
            data = {"slug": slug, "url": url, "scraped_datetime": now, "races": data}
        else:
            data["slug"] = slug
            data["url"] = url
            data["scraped_datetime"] = now

        # Write out a timestamped file
        folder_name = f"{slug.split('/')[0]}"
        timestamp_path = (
            utils.RAW_DATA_DIR
            / "ca_secretary_of_state"
            / folder_name
            / f"{utils.now().isoformat()}.json"
        )
        utils.write_json(data, timestamp_path)

        # Overwrite the latest file
        latest_path = (
            utils.RAW_DATA_DIR / "ca_secretary_of_state" / folder_name / "latest.json"
        )
        utils.write_json(data, latest_path)


if __name__ == "__main__":
    cli()
