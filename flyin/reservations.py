from flyin.models import Connection, Network, Position


class ReservationTable:
    """Counts how many drones use each zone and link at every turn"""

    def __init__(self, network: Network) -> None:
        """Empty table, nothing booked yet"""
        self._network = network
        self._zones: dict[tuple[str, int], int] = {}
        self._links: dict[tuple[tuple[str, str], int], int] = {}

    def zone_has_room(self, zone_name: str, turn: int) -> bool:
        """Can one more drone sit in this zone at the end of `turn`"""
        used = self._zones.get((zone_name, turn), 0)
        return self._network.zones[zone_name].fits(used + 1)

    def link_has_room(self, link: Connection, turn: int) -> bool:
        """Can one more drone fly over this link during `turn`"""
        used = self._links.get((link.key, turn), 0)
        return used < link.max_capacity

    def reserve(self, timeline: list[Position]) -> None:
        """Book everything a drone uses along its timeline"""
        for turn in range(1, len(timeline)):
            before, now = timeline[turn - 1], timeline[turn]
            if now.connection is not None:
                # took off toward a restricted zone, only the link is busy
                key = (now.connection.key, turn)
                self._links[key] = self._links.get(key, 0) + 1
            elif now.zone is not None:
                spot = (now.zone, turn)
                self._zones[spot] = self._zones.get(spot, 0) + 1
                if before.zone is not None and before.zone != now.zone:
                    # a normal one-turn move, so the link was used too
                    link = self._network.connection_between(
                        before.zone, now.zone)
                    if link is None:
                        raise ValueError(
                            f"no link between {before.zone} and {now.zone}")
                    key = (link.key, turn)
                    self._links[key] = self._links.get(key, 0) + 1
