import csv
import json
import pathlib

import pytest

from src.los_angeles_county.transform import ContestTransformer

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture
def corrections():
    """Load LAC corrections fixture as a dict keyed by raw_name."""
    return {
        d["raw_name"]: d
        for d in csv.DictReader(open(FIXTURES_DIR / "lac_corrections.csv"))
    }


@pytest.fixture
def contest(corrections):
    """Return a LAC ContestTransformer loaded from fixture data."""
    raw = json.load(open(FIXTURES_DIR / "lac_contest.json"))
    return ContestTransformer(raw, corrections)


def test_include(contest):
    """Contest marked include=yes in corrections should be included."""
    assert contest.include() is True


def test_name(contest):
    """Contest name comes from corrections clean_name."""
    assert contest.dump()["name"] == "Sheriff"


def test_slug(contest):
    """Slug is slugified from clean_name."""
    assert contest.dump()["slug"] == "sheriff"


def test_geography(contest):
    """Geography comes from corrections clean_geography."""
    assert contest.dump()["geography"] == "Los Angeles County"


def test_sort_order(contest):
    """Sort order comes from corrections sort_order column."""
    assert contest.dump()["sort_order"] == 1


def test_votes_percent_sums_to_one(contest):
    """Candidate vote percentages should sum to 1.0."""
    candidates = contest.dump()["candidates"]
    total = round(sum(c["votes_percent"] for c in candidates), 4)
    assert total == 1.0


def test_incumbent_marked(contest):
    """Candidate flagged in corrections as incumbent should have incumbent=True."""
    candidates = contest.dump()["candidates"]
    incumbents = [c for c in candidates if c["incumbent"]]
    assert len(incumbents) == 1
    assert incumbents[0]["name"] == "Alex Villanueva"


def test_non_incumbent_not_marked(contest):
    """Candidate not flagged as incumbent should have incumbent=False."""
    candidates = contest.dump()["candidates"]
    non_incumbents = [c for c in candidates if not c["incumbent"]]
    assert len(non_incumbents) == 1
    assert non_incumbents[0]["name"] == "John Smith"
