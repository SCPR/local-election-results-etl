import typing

from pydantic import BaseModel


class CandidateResult(BaseModel):
    """A standardized instance of a candidate's vote totals."""

    name: str
    party: typing.Optional[str]
    votes: int
    votes_percent: float
    incumbent: typing.Optional[bool]


class Contest(BaseModel):
    """An election contest or race."""

    name: str
    slug: str
    description: typing.Optional[str]
    geography: typing.Optional[str]
    level: typing.Optional[str]
    precincts_reporting: typing.Optional[str]
    candidates: typing.List[CandidateResult]
    sort_order: typing.Optional[int] = None


class BaseTransformer:
    """A base transformer for all of our files."""

    model: typing.Any = None

    def __init__(
        self, raw_data: typing.Dict, corrections: typing.Optional[typing.Dict] = None
    ):
        """Create a new object."""
        self.raw = raw_data
        self.corrections = corrections
        self._transformed: typing.Optional[typing.Dict] = None

    def dump(self) -> typing.Dict:
        """Transform, validate, and dump the object. Only called after include() passes."""
        if self._transformed is None:
            self._transformed = self.transform_data()
            self.model(**self._transformed)
        return self.model(**self._transformed).model_dump()

    def transform_data(self):
        """Map the raw data to our schema fields."""
        raise NotImplementedError()
