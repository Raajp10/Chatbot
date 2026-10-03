"""Source parsers: raw webpage/PDF bytes → ordered `Block`s with heading/page structure."""


class ParseError(Exception):
    """The fetched content can't be turned into meaningful text."""
