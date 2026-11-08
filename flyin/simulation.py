from flyin.models import Drone, Network, Position


class Simulation:
    """Turns the drone timelines into turn-by-turn moves"""

    def __init__(self, network: Network, drones: list[Drone]) -> None:
        """Keep the planned drones and work out how long the run takes"""
        self.network = network
        self.drones = drones
        self.total_turns: int = max(
            (drone.arrival_turn for drone in drones), default=0)

    def moves_at(self, turn: int) -> list[tuple[Drone, Position]]:
        """Drones that move during `turn` and where they end up"""
        moves: list[tuple[Drone, Position]] = []
        for drone in self.drones:
            if turn > drone.arrival_turn:
                continue  # already delivered, not tracked anymore
            now = drone.position_at(turn)
            if now != drone.position_at(turn - 1):
                moves.append((drone, now))
        return moves

    def line_at(self, turn: int) -> str:
        """One output line, e.g. 'D1-roof1 D2-corridorA'"""
        return " ".join(
            f"{drone.name}-{pos.label}" for drone, pos in self.moves_at(turn))

    def lines(self) -> list[str]:
        """Every output line from turn 1 to the last arrival"""
        return [self.line_at(turn) for turn in range(1, self.total_turns + 1)]
