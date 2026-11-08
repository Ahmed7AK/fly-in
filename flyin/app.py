import argparse
import os
import sys

from flyin.distances import DistanceMap
from flyin.errors import FlyInError
from flyin.parser import MapParser
from flyin.scheduler import Scheduler
from flyin.simulation import Simulation
from flyin.terminal_view import TerminalView


class FlyInApp:
    """Glues every piece together and handles the command line"""

    def __init__(self, argv: list[str]) -> None:
        """Read the command line arguments"""
        parser = argparse.ArgumentParser(
            prog="fly-in", description="Route drones from start to end.")
        parser.add_argument("map", help="path to the map file")
        parser.add_argument("--no-gui", action="store_true",
                            help="only print the moves, no pygame window")
        args = parser.parse_args(argv)
        self._map_path: str = args.map
        self._gui: bool = not args.no_gui

    def run(self) -> int:
        """Run the whole thing and return the exit code"""
        try:
            simulation = self._simulate()
            TerminalView(simulation).show()
            if self._gui:
                self._open_window(simulation)
        except FlyInError as err:
            return self._fail(str(err))
        except OSError as err:
            return self._fail(f"can't read '{self._map_path}': "
                              f"{err.strerror}")
        except KeyboardInterrupt:
            return self._fail("interrupted")
        except Exception as err:  # last line of defense, never a traceback
            return self._fail(f"unexpected {type(err).__name__}: {err}")
        return 0

    @staticmethod
    def _open_window(simulation: Simulation) -> None:
        """Show the pygame window, or just skip it if that can't work"""
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        try:
            from flyin.pygame_view import PygameView
            PygameView(simulation).run()
        except (ImportError, RuntimeError) as err:  # no pygame / no display
            print(f"No window ({err}), terminal output only",
                  file=sys.stderr)

    def _simulate(self) -> Simulation:
        """Parse, plan and build the simulation"""
        network = MapParser().parse(self._map_path)
        distances = DistanceMap(network)
        drones = Scheduler(network, distances).plan_all()
        return Simulation(network, drones)

    @staticmethod
    def _fail(message: str) -> int:
        """Print an error the nice way and give back exit code 1"""
        print(f"Error: {message}", file=sys.stderr)
        return 1
