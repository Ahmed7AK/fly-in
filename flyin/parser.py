import re

from flyin.errors import ParseError
from flyin.models import Connection, Network, Zone, ZoneType


class MapParser:
    """Reads a map file and turns it into a Network"""

    # prefix -> (is_start, is_end)
    ZONE_PREFIXES: dict[str, tuple[bool, bool]] = {
        "start_hub": (True, False),
        "end_hub": (False, True),
        "hub": (False, False),
    }
    ZONE_KEYS: frozenset[str] = frozenset({"zone", "color", "max_drones"})
    CONNECTION_KEYS: frozenset[str] = frozenset({"max_link_capacity"})

    def __init__(self) -> None:
        """Nothing parsed yet"""
        self._network: Network | None = None

    def parse(self, path: str) -> Network:
        """Parse the whole file, stops at the first problem"""
        self._network = None
        with open(path, encoding="utf-8") as file:
            try:
                for line_no, raw in enumerate(file, start=1):
                    self._parse_line(line_no, raw)
            except UnicodeDecodeError as err:
                raise ParseError(0, "file is not valid UTF-8 text") from err
        return self._finish()

    def _parse_line(self, line_no: int, raw: str) -> None:
        """Handle one line, turning any ValueError into a ParseError"""
        line = raw.split("#", 1)[0].strip()
        if not line:
            return
        prefix, _, rest = line.partition(":")
        try:
            self._dispatch(prefix.strip(), rest.strip())
        except ValueError as err:
            raise ParseError(line_no, str(err)) from err

    def _dispatch(self, prefix: str, rest: str) -> None:
        """Send the line to the right handler based on its prefix"""
        if self._network is None:
            if prefix != "nb_drones":
                raise ValueError(
                    "first line must be 'nb_drones: <positive_integer>'")
            self._network = Network(self._positive_int(rest, "nb_drones"))
        elif prefix in self.ZONE_PREFIXES:
            self._parse_zone(self._network, prefix, rest)
        elif prefix == "connection":
            self._parse_connection(self._network, rest)
        elif prefix == "nb_drones":
            raise ValueError("nb_drones is defined twice")
        else:
            raise ValueError(f"unknown line type '{prefix}'")

    def _parse_zone(self, network: Network, prefix: str, rest: str) -> None:
        """start_hub / end_hub / hub: <name> <x> <y> [metadata]"""
        body, tags = self._split_metadata(rest, self.ZONE_KEYS)
        parts = body.split()
        if len(parts) != 3:
            raise ValueError(f"expected '{prefix}: <name> <x> <y> [metadata]'")
        name, x, y = parts
        if "-" in name:
            raise ValueError(f"zone name '{name}' can't contain a dash")
        is_start, is_end = self.ZONE_PREFIXES[prefix]
        max_drones = 1
        if not (is_start or is_end):  # capacity is ignored on start/end
            max_drones = self._positive_int(
                tags.get("max_drones", "1"), "max_drones")
        network.add_zone(Zone(
            name=name,
            x=self._int(x, "x"),
            y=self._int(y, "y"),
            zone_type=self._zone_type(tags.get("zone", "normal")),
            color=tags.get("color"),
            max_drones=max_drones,
            is_start=is_start,
            is_end=is_end,
        ))

    def _parse_connection(self, network: Network, rest: str) -> None:
        """connection: <zone1>-<zone2> [metadata]"""
        body, tags = self._split_metadata(rest, self.CONNECTION_KEYS)
        ends = body.split("-")
        if len(body.split()) != 1 or len(ends) != 2 or "" in ends:
            raise ValueError(
                "expected 'connection: <zone1>-<zone2> [metadata]'")
        capacity = self._positive_int(
            tags.get("max_link_capacity", "1"), "max_link_capacity")
        network.add_connection(Connection(ends[0], ends[1], capacity))

    def _split_metadata(
        self, text: str, allowed: frozenset[str]
    ) -> tuple[str, dict[str, str]]:
        """Split 'body [k=v k=v]' into the body and a dict of tags"""
        if "[" not in text:
            if "]" in text:
                raise ValueError("found ']' without an opening '['")
            return text, {}
        body, _, meta = text.partition("[")
        if not meta.endswith("]"):
            raise ValueError("metadata must end with ']' and end the line")
        meta = meta[:-1]
        if "[" in meta or "]" in meta:
            raise ValueError("only one [...] block is allowed per line")
        tags: dict[str, str] = {}
        for token in meta.split():
            key, sep, value = token.partition("=")
            if not sep or not key or not value:
                raise ValueError(f"bad tag '{token}', expected key=value")
            if key not in allowed:
                raise ValueError(f"unknown metadata key '{key}'")
            if key in tags:
                raise ValueError(f"metadata key '{key}' given twice")
            tags[key] = value
        return body.strip(), tags

    def _finish(self) -> Network:
        """Last checks once the whole file has been read"""
        if self._network is None:
            raise ParseError(0, "empty map, expected 'nb_drones: <number>'")
        try:
            self._network.check_complete()
        except ValueError as err:
            raise ParseError(0, str(err)) from err
        return self._network

    @staticmethod
    def _int(text: str, what: str) -> int:
        """Strict integer, so things like '3.5' or '1e3' get rejected"""
        if not re.fullmatch(r"-?[0-9]+", text):
            raise ValueError(f"{what} must be an integer, got '{text}'")
        return int(text)

    @staticmethod
    def _positive_int(text: str, what: str) -> int:
        """Integer that has to be at least 1"""
        if not re.fullmatch(r"[0-9]+", text) or int(text) < 1:
            raise ValueError(f"{what} must be a positive integer, "
                             f"got '{text}'")
        return int(text)

    @staticmethod
    def _zone_type(text: str) -> ZoneType:
        """Map the zone=... value to a ZoneType"""
        try:
            return ZoneType(text)
        except ValueError:
            raise ValueError(
                f"invalid zone type '{text}' "
                "(use normal, blocked, restricted or priority)") from None
