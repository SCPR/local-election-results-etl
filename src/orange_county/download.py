import re

import click
from bs4 import BeautifulSoup

from .. import utils

# OC publishes its live ENR URL on this page before each election.
# We scrape it to discover the current election's data endpoint.
OC_RESULTS_PAGE = "https://www.ocvote.gov/results/current-election-results"

# The ENR system (livevoterturnout.com) follows this URL pattern:
#   https://www.livevoterturnout.com/ENR/orangecaenr/{n}/en/{hash}_Index_{n}.html
# The JSON summary data is at:
#   https://www.livevoterturnout.com/ENR/orangecaenr/{n}/en/{hash}_Summary.json
# The contest list is at:
#   https://www.livevoterturnout.com/ENR/orangecaenr/{n}/en/{hash}_ContestResults_{n}.json
#
# NOTE: These URLs are not live until OC publishes the ENR link on their results
# page, typically 1-2 weeks before election day. Verify the schema against a
# live election before completing transform.py.


def get_enr_base(enr_index_url: str) -> tuple:
    """Extract (base_url, election_num, hash) from an ENR index URL."""
    # e.g. https://www.livevoterturnout.com/ENR/orangecaenr/22/en/pk993bj_Index_22.html
    match = re.search(
        r"(https://www\.livevoterturnout\.com/ENR/orangecaenr/(\d+)/en/)([a-z0-9]+)_Index_\d+\.html",
        enr_index_url,
    )
    if not match:
        raise ValueError(f"Could not parse ENR index URL: {enr_index_url}")
    base_url = match.group(1)
    election_num = match.group(2)
    hash_key = match.group(3)
    return base_url, election_num, hash_key


@click.command()
@click.option(
    "--election",
    default=None,
    help="Election config name from elections/ dir (e.g. 2026-june-primary)",
)
@click.option(
    "--enr-url",
    "enr_url",
    default=None,
    help="Override the ENR index URL directly (e.g. from ocvote.gov results page)",
)
def cli(election, enr_url):
    """Download JSON data posted by the Orange County Registrar."""
    # Resolve the ENR index URL
    if enr_url is None:
        if election:
            config = utils.load_election_config(election)
            enr_url = config["sources"].get("orange_county", {}).get("enr_url")
        if enr_url is None:
            # Scrape the OC results page to find the current ENR link
            print(f"🔍 Scraping {OC_RESULTS_PAGE} for ENR link")
            html = utils.request_html(OC_RESULTS_PAGE)
            soup = BeautifulSoup(html, "html.parser")
            link = soup.find("a", href=re.compile(r"livevoterturnout\.com"))
            if not link:
                raise RuntimeError(
                    "Could not find a livevoterturnout.com link on the OC results page. "
                    "The ENR may not be live yet. Pass --enr-url to override."
                )
            enr_url = link["href"]

    base_url, election_num, hash_key = get_enr_base(enr_url)

    # Fetch the summary JSON (overall stats + contest list)
    summary_url = f"{base_url}{hash_key}_Summary.json"
    summary = utils.request_json(summary_url)

    # Fetch the full contest results JSON
    contests_url = f"{base_url}{hash_key}_ContestResults_{election_num}.json"
    data = utils.request_json(contests_url)

    # Attach metadata
    now = utils.now().isoformat()
    payload = {
        "enr_url": enr_url,
        "summary_url": summary_url,
        "contests_url": contests_url,
        "scraped_datetime": now,
        "summary": summary,
        "contests": data,
    }

    # Write out a timestamped file
    timestamp_path = (
        utils.RAW_DATA_DIR / "orange_county" / f"{now}.json"
    )
    utils.write_json(payload, timestamp_path)

    # Overwrite the latest file
    latest_path = utils.RAW_DATA_DIR / "orange_county" / "latest.json"
    utils.write_json(payload, latest_path)


if __name__ == "__main__":
    cli()
