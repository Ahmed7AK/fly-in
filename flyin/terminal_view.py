import sys

from flyin.models import Drone, Position
from flyin.simulation import Simulation


class TerminalView:
    """Prints the moves, colored by destination zone in a real terminal"""

    # map color name -> ANSI color code
    ANSI: dict[str, str] = {
        "black": "30", "red": "31", "green": "32", "yellow": "33",
        "blue": "34", "magenta": "35", "purple": "35", "cyan": "36",
        "white": "37", "gray": "90", "grey": "90", "orange": "38;5;208",
        "pink": "38;5;213", "brown": "38;5;130",
    }

    def __init__(self, simulation: Simulation) -> None:
        """Only use colors when we're not piped into a file"""
        self._sim = simulation
        self._colored = sys.stdout.isatty()

    def show(self) -> None:
        """Print every turn, then a short summary on stderr"""
        for turn in range(1, self._sim.total_turns + 1):
            print(" ".join(self._paint(drone, pos, turn)
                           for drone, pos in self._sim.moves_at(turn)))
        sys.stdout.flush()  # keep the summary after the moves when piped
        print(f"{len(self._sim.drones)} drones delivered in "
              f"{self._sim.total_turns} turns", file=sys.stderr)

    def _paint(self, drone: Drone, pos: Position, turn: int) -> str:
        """One 'D1-zone' piece, colored like the zone it's heading to"""
        text = f"{drone.name}-{pos.label}"
        # a drone in transit gets the color of the zone it lands in next
        target = drone.position_at(turn + 1) if pos.in_transit else pos
        zone = self._sim.network.zones.get(str(target.zone))
        code = self.ANSI.get((zone.color or "").lower()) if zone else None
        if not self._colored or code is None:
            return text
        return f"\033[{code}m{text}\033[0m"
