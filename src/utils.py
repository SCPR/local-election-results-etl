import json
import os
import pathlib
import typing
from datetime import datetime

import boto3
import pytz
import requests
from retry import retry
from rich import print

THIS_DIR = pathlib.Path(__file__).parent.absolute()
ROOT_DIR = THIS_DIR.parent
DATA_DIR = ROOT_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
TRANSFORMED_DATA_DIR = DATA_DIR / "transformed"


def now() -> datetime:
    """Return the current time in our local timezone."""
    now = datetime.now()
    tz = pytz.timezone("America/Los_Angeles")
    return now.astimezone(tz)


@retry()
def request_json(url: str) -> typing.Dict:
    """Request the provided URL and return the JSON response as a Python dictionary."""
    print(f"🌐 Requesting JSON from {url}")
    headers = {
        "User-Agent": "BIG LOCAL NEWS (palewire@stanford.edu)",
    }
    r = requests.get(url, headers=headers)
    assert r.ok
    return r.json()


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


def get_latest_paths() -> typing.List[pathlib.Path]:
    """Return a list of the latest JSON files."""
    obj_list = TRANSFORMED_DATA_DIR.glob("**/*")
    return [o for o in obj_list if o.is_file() and "latest.json" in str(o)]
