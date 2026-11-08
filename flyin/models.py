from dataclasses import dataclass, field
from enum import Enum


class ZoneType(Enum):
    """Type of a zone each value is the string used in map files"""

    NORMAL = "normal"
    BLOCKED = "blocked"
    RESTRICTED = "restricted"
    PRIORITY = "priority"

    @property
    def cost(self) -> int:
        """Number of turns needed to move into a zone"""
        return 2 if self is ZoneType.RESTRICTED else 1

    @property
    def passable(self) -> bool:
        """Whether drones are ever allowed to enter this zone type"""
        return self is not ZoneType.BLOCKED


@dataclass
class Zone:
    """A node of the network (a hub)."""

    name: str
    x: int
    y: int
    zone_type: ZoneType = ZoneType.NORMAL
    color: str | None = None
    max_drones: int = 1
    is_start: bool = False
    is_end: bool = False

    @property
    def unlimited(self) -> bool:
        """Start and end zones have no capacity limit."""
        return self.is_start or self.is_end

    def fits(self, count: int) -> bool:
        """Return True if `count` drones may occupy this zone at once."""
        return self.unlimited or count <= self.max_drones


@dataclass(frozen=True)
class Connection:
    """A bidirectional edge between two zones (stored by zone name)."""

    zone_a: str
    zone_b: str
    max_capacity: int = 1

    @property
    def key(self) -> tuple[str, str]:
        """Order-independent identity: a-b and b-a give the same key."""
        if self.zone_a <= self.zone_b:
            return (self.zone_a, self.zone_b)
        return (self.zone_b, self.zone_a)

    @property
    def name(self) -> str:
        """Name as written in the map file, used in the output."""
        return f"{self.zone_a}-{self.zone_b}"

    def other(self, zone_name: str) -> str:
        """Return the zone at the opposite end from `zone_name`."""
        if zone_name == self.zone_a:
            return self.zone_b
        if zone_name == self.zone_b:
            return self.zone_a
        raise ValueError(f"'{zone_name}' is not an end of {self.name}")


@dataclass(frozen=True)
class Position:
    """Where a drone is at the end of a turn."""

    zone: str | None = None
    connection: Connection | None = None

    def __post_init__(self) -> None:
        """Reject positions that are both or neither zone and link."""
        if (self.zone is None) == (self.connection is None):
            raise ValueError("Position needs exactly one of zone/connection")

    @classmethod
    def at(cls, zone_name: str) -> "Position":
        """Build a position inside a zone."""
        return cls(zone=zone_name)

    @classmethod
    def on(cls, connection: Connection) -> "Position":
        """Build an in-transit position on a connection."""
        return cls(connection=connection)

    @property
    def in_transit(self) -> bool:
        """True when the drone is flying over a connection."""
        return self.connection is not None

    @property
    def label(self) -> str:
        """Text printed after 'D<id>-' in the simulation output."""
        if self.connection is not None:
            return self.connection.name
        return str(self.zone)


@dataclass
class Drone:
    """A drone and its planned timeline"""

    drone_id: int
    timeline: list[Position] = field(default_factory=list)

    @property
    def name(self) -> str:
        """Identifier used in the output, e.g. 'D3'."""
        return f"D{self.drone_id}"

    @property
    def arrival_turn(self) -> int:
        """Turn at which the drone reaches the end zone."""
        return len(self.timeline) - 1

    def position_at(self, turn: int) -> Position:
        """Position at `turn`; after arrival the drone stays at the end."""
        return self.timeline[min(turn, self.arrival_turn)]


class Network:
    """Graph of zones linked by bidirectional connections."""

    def __init__(self, nb_drones: int) -> None:
        """Create an empty network that will route `nb_drones` drones."""
        self.nb_drones: int = nb_drones
        self.zones: dict[str, Zone] = {}
        self.connections: dict[tuple[str, str], Connection] = {}
        self.adjacency: dict[str, list[Connection]] = {}
        self._start: str | None = None
        self._end: str | None = None

    def add_zone(self, zone: Zone) -> None:
        """Register a zone; raise ValueError if it breaks a rule."""
        if zone.name in self.zones:
            raise ValueError(f"duplicate zone name '{zone.name}'")
        if zone.is_start:
            if self._start is not None:
                raise ValueError("more than one start_hub")
            self._start = zone.name
        if zone.is_end:
            if self._end is not None:
                raise ValueError("more than one end_hub")
            self._end = zone.name
        self.zones[zone.name] = zone
        self.adjacency[zone.name] = []

    def add_connection(self, connection: Connection) -> None:
        """Register a connection; raise ValueError if it breaks a rule."""
        for name in (connection.zone_a, connection.zone_b):
            if name not in self.zones:
                raise ValueError(f"unknown zone '{name}' in connection")
        if connection.zone_a == connection.zone_b:
            raise ValueError("a zone cannot be connected to itself")
        if connection.key in self.connections:
            raise ValueError(f"duplicate connection '{connection.name}'")
        self.connections[connection.key] = connection
        self.adjacency[connection.zone_a].append(connection)
        self.adjacency[connection.zone_b].append(connection)

    @property
    def start(self) -> Zone:
        """The start zone (raises ValueError if none was defined)."""
        if self._start is None:
            raise ValueError("missing start_hub")
        return self.zones[self._start]

    @property
    def end(self) -> Zone:
        """The end zone (raises ValueError if none was defined)."""
        if self._end is None:
            raise ValueError("missing end_hub")
        return self.zones[self._end]

    def check_complete(self) -> None:
        """Make sure both a start and an end hub were defined"""
        if self._start is None:
            raise ValueError("missing start_hub")
        if self._end is None:
            raise ValueError("missing end_hub")

    def neighbors(self, zone_name: str) -> list[tuple[Zone, Connection]]:
        """Return (neighbor zone, connection used) pairs of a zone."""
        return [
            (self.zones[conn.other(zone_name)], conn)
            for conn in self.adjacency[zone_name]
        ]

    def connection_between(self, a: str, b: str) -> Connection | None:
        """Return the connection linking zones a and b, if any."""
        key = (a, b) if a <= b else (b, a)
        return self.connections.get(key)
