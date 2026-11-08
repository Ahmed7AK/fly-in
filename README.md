*This project has been created as part of the 42 curriculum by <login>.*

# Fly-in

## Description

Fly-in routes a fleet of drones from a start hub to an end hub through a
network of connected zones, in as few simulation turns as possible.

Every zone and every connection has a capacity, some zones are slower to
enter (restricted), some are preferred (priority) and some can't be entered
at all (blocked). All drones move at the same time, turn by turn, and no
rule may ever be broken. The program:

1. parses a map file and validates it (clear error with the line number),
2. detects maps that can't be solved (start not connected to the end),
3. plans a collision-free route for every drone,
4. prints the moves turn by turn in the required format,
5. animates the whole thing in a pygame window.

Written in Python 3.10+, fully object-oriented and typed (flake8 + mypy
clean). No graph library is used: the graph and every algorithm are written
by hand.

## Instructions

```bash
make install                         # creates .venv and installs requirements
make run                             # runs maps/example.txt
make run MAP=maps/hard/some_map.txt  # runs another map
make debug                           # same as run, inside pdb
make lint                            # flake8 + mypy (subject flags)
make lint-strict                     # flake8 + mypy --strict
make clean                           # removes caches
```

Or directly:

```bash
.venv/bin/python main.py <map_file>            # moves + pygame window
.venv/bin/python main.py <map_file> --no-gui   # moves only
```

The moves are printed on stdout, a one-line summary on stderr. If no window
can be opened (no display, pygame missing), the program keeps the terminal
output and says so instead of crashing.

### Map format

```
nb_drones: 5
start_hub: hub 0 0 [color=green]
end_hub: goal 10 10 [color=yellow]
hub: roof1 3 4 [zone=restricted color=red]
hub: corridorA 4 3 [zone=priority color=green max_drones=2]
connection: hub-roof1
connection: corridorA-tunnelB [max_link_capacity=2]
# comments start with '#'
```

| Zone type    | Cost to enter | Notes                                  |
|--------------|---------------|----------------------------------------|
| `normal`     | 1 turn        | default                                |
| `priority`   | 1 turn        | preferred when two routes are as fast  |
| `restricted` | 2 turns       | the drone spends one turn on the link  |
| `blocked`    | never         | no path may use it                     |

## Example

Input: [`maps/example.txt`](maps/example.txt) (the example from the subject).

Output (`make run`):

```
D1-corridorA D2-hub-roof1
D1-tunnelB D2-roof1 D3-corridorA D4-hub-roof1
D1-goal D2-roof2 D3-tunnelB D4-roof1 D5-corridorA
D2-goal D3-goal D4-roof2 D5-tunnelB
D4-goal D5-goal
5 drones delivered in 5 turns
```

The drones split over the two lanes by themselves: odd drones take the
priority corridor (3 turns), even drones take the restricted roof (4 turns,
`D2-hub-roof1` is the turn spent flying over the link). 5 turns is the
optimum for this map.

Errors look like this:

```
Error: line 4: invalid zone type 'fast' (use normal, blocked, restricted or priority)
Error: no path from 'A' to 'B'
Error: can't read 'maps/nope.txt': No such file or directory
```

## Algorithm and implementation

### Pipeline

```
map file -> MapParser -> Network -> DistanceMap -> Scheduler -> Simulation -> views
                                                       |
                                               ReservationTable
```

| File | Class | Job |
|---|---|---|
| `flyin/models.py` | `ZoneType`, `Zone`, `Connection`, `Position`, `Drone`, `Network` | data model, adjacency-list graph |
| `flyin/parser.py` | `MapParser` | strict parsing, line-numbered errors |
| `flyin/distances.py` | `DistanceMap` | reverse Dijkstra, unsolvable-map detection |
| `flyin/reservations.py` | `ReservationTable` | zone/link usage per turn |
| `flyin/scheduler.py` | `Scheduler` | time-aware A* per drone |
| `flyin/simulation.py` | `Simulation` | output lines |
| `flyin/terminal_view.py`, `flyin/pygame_view.py` | `TerminalView`, `PygameView` | visual output |
| `flyin/app.py` | `FlyInApp` | CLI and error handling |

A drone's plan is a **timeline**: one `Position` per turn (inside a zone, or
in transit on a link toward a restricted zone). The output and the
animation are both derived from these timelines.

### 1. Distances to the end (reverse Dijkstra)

For every zone we compute the fewest turns needed to reach the end if the
drone were alone. Entering a zone costs its type's cost, so the search runs
backwards from the end: `dist[u] = dist[v] + cost(v)`. Blocked zones are
skipped. If the start never gets a distance, the map is unsolvable and the
program says so (`NoPathError`) before simulating anything.

This is computed once and cached. It serves as an exact A* heuristic and
lets the scheduler ignore dead ends entirely.

Complexity: O(V² + E) (the closest zone is picked with a linear scan, maps
are small).

### 2. Rules as counting (reservation table)

- zone occupancy is counted at the end of each turn, so a zone freed during
  a turn is available in that same turn;
- a link is used on the turn a drone crosses it; both directions share the
  same counter, so head-on swaps through a capacity-1 link are impossible;
- a restricted move takes off on turn `t` (link used), lands on `t+1` (zone
  used, link freed); the zone must have room on `t+1` before take-off, so a
  drone never waits on a link;
- start and end zones have no capacity limit.

### 3. Prioritized planning with time-aware A*

Drones are planned one after another. Each one searches over
`(zone, turn)` states, so a zone that is full at turn 4 can still be used at
turn 5. From a state a drone can wait, move to a neighbor (1 turn) or start
a restricted move (2 turns), only if the reservation table has room. Once a
drone's route is found, it is booked in the table, and the next drone has to
work around it.

- `f = turn + distance_to_end`. States are kept in buckets indexed by `f`
  (small integers), so the open list costs O(1) per operation and needs no
  priority-queue library.
- `g` is always the turn number, so the first time a state is reached is
  the best; no state is ever revisited.
- Ties: priority zones are tried first (subject: "should be prioritized"),
  and buckets are read first-in first-out, which makes a drone that has to
  wait do it early, at the unlimited start zone, instead of mid-route where
  it would block the drones behind it.
- Horizon: a drone never needs more than `last_arrival + distance(start)`
  turns (wait until everyone landed, then fly alone), so the search always
  ends.

Correct by construction: every drone only uses capacity left over by the
previous ones. Always terminates: the start zone is unlimited, so a drone
can always wait there.

Complexity: per drone O((V + E) × H) states in the worst case (H = horizon),
usually far less since A* follows the heuristic. Paths are computed once
before the simulation and never recalculated. Memory: the reservation table
is O(drones × path length).

### Benchmarks

| Map | Drones | Optimum | Ours |
|---|---|---|---|
| easy/01_linear_path | 2 | 4 | 4 |
| easy/02_simple_fork | 4 | 4 | 4 |
| easy/03_basic_capacity | 4 | 4 | 4 |
| medium/01_dead_end_trap | 5 | 8 | 8 |
| medium/02_circular_loop | 6 | 10 | 10 |
| medium/03_priority_puzzle | 5 | 6 | 6 |
| hard/01_maze_nightmare | 8 | 13 | 13 |
| hard/02_capacity_hell | 12 | 16 | 16 |
| hard/03_ultimate_challenge | 15 | 26 | 26 |
| challenger/01_the_impossible_dream | 25 | 43 | 43 |
| example (subject chapter VI) | 5 | 5 | 5 |

Every map reaches its optimum, and the whole set is planned in well under
a second.

## Visual representation

**Terminal**: each move is colored with the color of the zone the drone is
heading to (a drone in transit takes the color of the zone it lands in).
Colors are only used in a real terminal; when the output is piped, it stays
plain so the format is exact.

**pygame window** (default, skip with `--no-gui`):

- zones drawn at their coordinates in their map color (any color name pygame
  knows, grey otherwise), start/end circled in white, blocked zones crossed
  out in red;
- each zone shows `drones/capacity`, the start shows how many drones are
  still waiting and the end how many are delivered, so bottlenecks are easy
  to spot;
- the map is stretched to fill the window, zone sizes follow the gap
  between the two closest zones, and each name goes below, above or beside
  its zone, wherever it doesn't overlap anything;
- links get thicker with their capacity (`x2` label);
- drones are numbered dots that slide smoothly between turns; a drone flying
  to a restricted zone stops halfway on the link for its in-transit turn;
- the bottom bar shows the turn, delivered count, speed and the exact output
  line of the current turn.

Controls: `SPACE` pause, `LEFT/RIGHT` step one turn, `UP/DOWN` speed,
`R` restart, `ESC` quit.

## Resources

- [Dijkstra's algorithm](https://en.wikipedia.org/wiki/Dijkstra%27s_algorithm)
- [A* search algorithm](https://en.wikipedia.org/wiki/A*_search_algorithm)
- [Red Blob Games: Introduction to A*](https://www.redblobgames.com/pathfinding/a-star/introduction.html)
- D. Silver, *Cooperative Pathfinding*, AIIDE 2005 — reservation tables
  and planning agents one by one
- [pygame documentation](https://www.pygame.org/docs/)
- [Python `dataclasses`](https://docs.python.org/3/library/dataclasses.html),
  [`enum`](https://docs.python.org/3/library/enum.html),
  [`argparse`](https://docs.python.org/3/library/argparse.html)
- [mypy](https://mypy.readthedocs.io/) and [flake8](https://flake8.pycqa.org/)

### AI usage

- I used Claude to break down the project into 

