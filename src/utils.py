import csv
import hashlib
import io
import json
import os
import pathlib
import typing
import zipfile
from datetime import datetime

import yaml

import boto3
import cloudscraper
import pytz
import requests
from retry import retry
from rich import print

THIS_DIR = pathlib.Path(__file__).parent.absolute()
ROOT_DIR = THIS_DIR.parent
DATA_DIR = ROOT_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
TRANSFORMED_DATA_DIR = DATA_DIR / "transformed"
OPTIMIZED_DATA_DIR = DATA_DIR / "optimized"


def now() -> datetime:
    """Return the current time in our local timezone."""
    now = datetime.now()
    tz = pytz.timezone("America/Los_Angeles")
    return now.astimezone(tz)


@retry(tries=3, delay=2, backoff=2)
def request_json(url: str) -> typing.Dict:
    """Request the provided URL and return the JSON response as a Python dictionary."""
    print(f"🌐 Requesting JSON from {url}")
    headers = {
        "User-Agent": "BIG LOCAL NEWS (palewire@stanford.edu)",
    }
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.json()


@retry(tries=3, delay=2, backoff=2)
def request_html(url: str) -> str:
    """Request the provided URL and return the HTML response as a string."""
    print(f"🌐 Requesting HTML from {url}")
    headers = {
        "User-Agent": "BIG LOCAL NEWS (palewire@stanford.edu)",
    }
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.text


@retry(tries=3, delay=2, backoff=2)
def request_zip(url: str) -> zipfile.ZipFile:
    """Request the provided URL and return a Zipfile object."""
    scraper = cloudscraper.create_scraper()
    r = scraper.get(url)
    r.raise_for_status()
    buffer = io.BytesIO(bytes(r.content))
    return zipfile.ZipFile(buffer)


def write_json(data: typing.Dict, path: pathlib.Path, indent: int = 2):
    """Write the provided data dictionary into the provided path."""
    print(f"✏️ Writing JSON to {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    json.dump(data, open(path, "w"), indent=indent, sort_keys=True)


def upload_to_s3(path: pathlib.Path, object_name: str):
    """Upload the provided file path as the provided object_name."""
    # Create client
    client = boto3.client("s3")

    # Get bucket
    bucket = os.getenv("AWS_BUCKET")

    # If there's a path prefix, tack it on
    path_prefix = os.getenv("AWS_PATH_PREFIX")
    if path_prefix:
        object_name = path_prefix + object_name

    # Log out
    print(f"Uploading {path} to {bucket} as {object_name}")

    # Upload it with our favored options
    client.upload_file(
        str(path),
        bucket,
        object_name,
        ExtraArgs={"ContentType": "application/json"},
    )


def load_election_config(name: str) -> typing.Dict:
    """Load an election configuration YAML from the elections/ directory."""
    config_path = ROOT_DIR / "elections" / f"{name}.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"No election config found at {config_path}")
    with open(config_path) as f:
        return yaml.safe_load(f)


def get_corrections_from_sheet(url: str) -> typing.Dict:
    """Fetch a corrections CSV from a published Google Sheet URL."""
    print(f"📋 Fetching corrections from {url}")
    r = requests.get(url)
    r.raise_for_status()
    reader = csv.DictReader(io.StringIO(r.text))
    return {d["raw_name"]: d for d in reader}


def get_ca_sos_slugs_from_endpoints(url: str) -> typing.List[str]:
    """Fetch the CA SOS API endpoints file and return top-level race slugs.

    Filters out county/district breakdowns, proposition sub-pages, status
    endpoints, and query-string URLs — keeping only the slugs we can transform.
    """
    print(f"📋 Fetching CA SOS endpoint list from {url}")
    r = requests.get(url)
    r.raise_for_status()
    base = "https://api.sos.ca.gov/returns/"
    slugs = []
    for line in r.text.splitlines():
        line = line.strip()
        if not line.startswith(base):
            continue
        if "?" in line:
            continue
        slug = line[len(base):]
        if "/county/" in slug:
            continue
        if "/prop/" in slug:
            continue
        if slug.startswith("status/"):
            continue
        slugs.append(slug)
    return slugs


def get_latest_paths() -> typing.List[pathlib.Path]:
    """Return a list of the latest transformed JSON files."""
    obj_list = TRANSFORMED_DATA_DIR.glob("**/*")
    return [o for o in obj_list if o.is_file() and "latest.json" in str(o)]


def get_hash_id(d: typing.Dict) -> str:
    """Convert a dict a unique hexdigest to use as a unique identifier.

    Args:
        dict (dict): One raw row of data from the source

    Returns: A unique hexdigest string computed from the source data.
    """
    d = d.copy()
    del d["candidates"]
    dict_string = json.dumps(d)
    hash_obj = hashlib.blake2b(digest_size=2)
    hash_obj.update(dict_string.encode("utf-8"))
    return hash_obj.hexdigest()
