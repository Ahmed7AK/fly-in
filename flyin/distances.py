from flyin.errors import NoPathError
from flyin.models import Network


class DistanceMap:
    """Fewest turns from each zone to the end, ignoring other drones"""

    def __init__(self, network: Network) -> None:
        """Compute everything once and bail out if the map can't be solved"""
        self._network = network
        self._dist: dict[str, int] = self._compute()
        start, end = network.start.name, network.end.name
        if start not in self._dist:
            raise NoPathError(f"no path from '{start}' to '{end}'")

    def turns_to_end(self, zone_name: str) -> int | None:
        """Turns needed to reach the end, None if it's a dead end"""
        return self._dist.get(zone_name)

    @property
    def from_start(self) -> int:
        """Turns the fastest drone needs, a lower bound for the whole run"""
        return self._dist[self._network.start.name]

    def _compute(self) -> dict[str, int]:
        """Dijkstra going backwards, starting from the end zone"""
        end = self._network.end
        if not end.zone_type.passable:
            return {}
        dist: dict[str, int] = {end.name: 0}
        done: set[str] = set()
        while True:
            todo = [name for name in dist if name not in done]
            if not todo:
                return dist
            name = min(todo, key=lambda n: dist[n])  # closest unfinished
            done.add(name)
            # any neighbor that steps into `name` pays the cost of `name`
            step = self._network.zones[name].zone_type.cost
            for neighbor, _ in self._network.neighbors(name):
                if not neighbor.zone_type.passable:
                    continue
                new_d = dist[name] + step
                if neighbor.name not in dist or new_d < dist[neighbor.name]:
                    dist[neighbor.name] = new_d
