from flyin.distances import DistanceMap
from flyin.errors import NoPathError
from flyin.models import Drone, Network, Position, ZoneType
from flyin.reservations import ReservationTable

State = tuple[str, int]  # (zone name, turn)


class Scheduler:
    """Plans drones one by one, each one dodging the ones before it"""

    def __init__(self, network: Network, distances: DistanceMap) -> None:
        """Start with an empty reservation table"""
        self._network = network
        self._distances = distances
        self._reservations = ReservationTable(network)

    def plan_all(self) -> list[Drone]:
        """Plan every drone in order and return them"""
        drones: list[Drone] = []
        last_arrival = 0
        for drone_id in range(1, self._network.nb_drones + 1):
            # worst case: wait at the start until everyone landed, then fly
            horizon = last_arrival + self._distances.from_start
            timeline = self._plan_one(horizon)
            self._reservations.reserve(timeline)
            drones.append(Drone(drone_id, timeline))
            last_arrival = max(last_arrival, len(timeline) - 1)
        return drones

    def _plan_one(self, horizon: int) -> list[Position]:
        """A* over (zone, turn) states, gives back the drone's timeline"""
        start: State = (self._network.start.name, 0)
        end = self._network.end.name
        parents: dict[State, State | None] = {start: None}
        # bucket f holds the states whose best possible arrival is turn f
        buckets: dict[int, list[State]] = {self._distances.from_start: [start]}
        for f in range(self._distances.from_start, horizon + 1):
            bucket = buckets.get(f, [])
            i = 0
            while i < len(bucket):  # the bucket can grow while we loop
                state = bucket[i]
                i += 1
                if state[0] == end:
                    return self._build_timeline(parents, state)
                for nxt, nxt_f in self._successors(state):
                    if nxt in parents or nxt_f > horizon:
                        continue
                    parents[nxt] = state
                    buckets.setdefault(nxt_f, []).append(nxt)
        raise NoPathError("couldn't fit a drone in the schedule")

    def _successors(self, state: State) -> list[tuple[State, int]]:
        """Every legal next state with its f score, preferred ones first"""
        zone, turn = state
        priority: list[tuple[State, int]] = []
        others: list[tuple[State, int]] = []
        for neighbor, link in self._network.neighbors(zone):
            h = self._distances.turns_to_end(neighbor.name)
            if h is None:
                continue  # blocked zone or dead end
            arrive = turn + neighbor.zone_type.cost
            if not self._reservations.link_has_room(link, turn + 1):
                continue
            if not self._reservations.zone_has_room(neighbor.name, arrive):
                continue
            if neighbor.zone_type is ZoneType.PRIORITY:
                priority.append(((neighbor.name, arrive), arrive + h))
            else:
                others.append(((neighbor.name, arrive), arrive + h))
        h_here = self._distances.turns_to_end(zone)
        if h_here is not None and self._reservations.zone_has_room(
                zone, turn + 1):
            others.append(((zone, turn + 1), turn + 1 + h_here))  # wait
        return priority + others

    def _build_timeline(
        self, parents: dict[State, State | None], goal: State
    ) -> list[Position]:
        """Walk back to the start, then add the in-transit turns"""
        path: list[State] = []
        state: State | None = goal
        while state is not None:
            path.append(state)
            state = parents[state]
        path.reverse()
        timeline = [Position.at(path[0][0])]
        for (prev_zone, prev_turn), (zone, turn) in zip(path, path[1:]):
            if turn - prev_turn == 2:  # restricted move, one turn on the link
                link = self._network.connection_between(prev_zone, zone)
                if link is None:
                    raise ValueError(f"no link between {prev_zone} and {zone}")
                timeline.append(Position.on(link))
            timeline.append(Position.at(zone))
        return timeline
