import math

import pygame

from flyin.models import Drone, Position, Zone
from flyin.simulation import Simulation

Point = tuple[float, float]


class PygameView:
    """Window that animates the drones flying through the network"""

    BACKGROUND = pygame.Color(24, 26, 33)
    LINK = pygame.Color(95, 100, 115)
    TEXT = pygame.Color(230, 230, 235)
    HUD = pygame.Color(36, 39, 48)
    DRONE = pygame.Color(255, 205, 70)
    BLOCKED = pygame.Color(55, 55, 60)
    DEFAULT_ZONE = pygame.Color(120, 130, 150)
    MARGIN = 70
    HUD_HEIGHT = 90

    def __init__(self, simulation: Simulation, turn_seconds: float = 0.8
                 ) -> None:
        """Set up fonts, colors and the animation clock"""
        pygame.init()
        self._sim = simulation
        self._network = simulation.network
        self._turn_seconds = turn_seconds
        self._turn = 0  # the turn we're animating from
        self._progress = 0.0  # 0 = at self._turn, 1 = at the next turn
        self._paused = False
        self._running = True
        self._font = pygame.font.Font(None, 20)
        self._big_font = pygame.font.Font(None, 28)
        self._label_font = pygame.font.Font(None, 17)
        self._labels: dict[str, pygame.Rect] = {}
        self._fitted_size = (0, 0)
        self._colors = {name: self._zone_color(zone)
                        for name, zone in self._network.zones.items()}
        # screen transform, recomputed every frame so resizing works
        self._scale: Point = (1.0, 1.0)  # x and y can stretch differently
        self._offset: Point = (0.0, 0.0)
        self._radius = 20

    def run(self) -> None:
        """Open the window and loop until the user closes it"""
        try:
            screen = pygame.display.set_mode((1200, 800), pygame.RESIZABLE)
            pygame.display.set_caption("Fly-in")
            clock = pygame.time.Clock()
            while self._running:
                dt = clock.tick(60) / 1000
                for event in pygame.event.get():
                    self._handle(event)
                self._advance(dt)
                self.draw(screen)
                pygame.display.flip()
        finally:
            pygame.quit()

    def draw(self, screen: pygame.Surface) -> None:
        """Draw one full frame"""
        self._fit(screen.get_size())
        screen.fill(self.BACKGROUND)
        for link in self._network.connections.values():
            self._draw_link(screen, link.zone_a, link.zone_b,
                            link.max_capacity)
        occupancy = self._occupancy()
        for zone in self._network.zones.values():
            self._draw_zone(screen, zone, occupancy.get(zone.name, 0))
        for drone in self._sim.drones:
            self._draw_drone(screen, drone)
        self._draw_hud(screen)

    # ---- input and timing ----

    def _handle(self, event: pygame.event.Event) -> None:
        """Keyboard controls and closing the window"""
        if event.type == pygame.QUIT:
            self._running = False
        elif event.type != pygame.KEYDOWN:
            return
        elif event.key in (pygame.K_ESCAPE, pygame.K_q):
            self._running = False
        elif event.key == pygame.K_SPACE:
            self._paused = not self._paused
        elif event.key == pygame.K_RIGHT:
            self._jump(1)
        elif event.key == pygame.K_LEFT:
            self._jump(-1)
        elif event.key in (pygame.K_UP, pygame.K_EQUALS, pygame.K_PLUS):
            self._turn_seconds = max(0.1, self._turn_seconds / 1.5)
        elif event.key in (pygame.K_DOWN, pygame.K_MINUS):
            self._turn_seconds = min(5.0, self._turn_seconds * 1.5)
        elif event.key == pygame.K_r:
            self._turn, self._progress = 0, 0.0

    def _jump(self, step: int) -> None:
        """Pause and move a whole turn forward or back"""
        self._paused = True
        self._turn = max(0, min(self._sim.total_turns, self._turn + step))
        self._progress = 0.0

    def _advance(self, dt: float) -> None:
        """Move the animation forward by dt seconds"""
        if self._paused or self._turn >= self._sim.total_turns:
            return
        self._progress += dt / self._turn_seconds
        while self._progress >= 1.0 and self._turn < self._sim.total_turns:
            self._progress -= 1.0
            self._turn += 1
        if self._turn >= self._sim.total_turns:
            self._progress = 0.0

    # ---- coordinates ----

    def _fit(self, size: tuple[int, int]) -> None:
        """Scale and center the map coordinates inside the window"""
        xs = [zone.x for zone in self._network.zones.values()]
        ys = [zone.y for zone in self._network.zones.values()]
        span_x, span_y = max(max(xs) - min(xs), 1), max(max(ys) - min(ys), 1)
        width = size[0] - 2 * self.MARGIN
        height = size[1] - self.HUD_HEIGHT - 2 * self.MARGIN
        # use the whole window, but don't stretch one axis more than 3x
        scale_x = max(width / span_x, 1.0)
        scale_y = max(min(height / span_y, scale_x * 3), 1.0)
        scale_x = min(scale_x, scale_y * 3)
        self._scale = (scale_x, scale_y)
        left = (size[0] - span_x * scale_x) / 2 - min(xs) * scale_x
        top = ((size[1] - self.HUD_HEIGHT - span_y * scale_y) / 2
               - min(ys) * scale_y)
        self._offset = (left, top)
        if size != self._fitted_size:  # only redo this when the size changes
            self._fitted_size = size
            # small enough that the two closest zones don't touch
            self._radius = max(8, min(28, int(self._closest_pair() * 0.3)))
            self._labels = self._place_labels()

    def _zone_point(self, name: str) -> Point:
        """Pixel position of a zone's center"""
        zone = self._network.zones[name]
        return (self._offset[0] + zone.x * self._scale[0],
                self._offset[1] + zone.y * self._scale[1])

    def _point(self, pos: Position) -> Point:
        """Pixel position of a drone position, mid-link when in transit"""
        if pos.connection is not None:
            a = self._zone_point(pos.connection.zone_a)
            b = self._zone_point(pos.connection.zone_b)
            return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        return self._zone_point(str(pos.zone))

    # ---- drawing ----

    def _draw_link(self, screen: pygame.Surface, a: str, b: str,
                   capacity: int) -> None:
        """A line between two zones, thicker when more drones fit"""
        start, end = self._zone_point(a), self._zone_point(b)
        pygame.draw.line(screen, self.LINK, start, end,
                         min(2 + 2 * (capacity - 1), 10))
        if capacity > 1:
            mid = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
            self._text(screen, f"x{capacity}", mid, self.TEXT)

    def _draw_zone(self, screen: pygame.Surface, zone: Zone,
                   count: int) -> None:
        """A circle in the zone's color with its name and how full it is"""
        center = self._zone_point(zone.name)
        color = self._colors[zone.name]
        pygame.draw.circle(screen, color, center, self._radius)
        if zone.is_start or zone.is_end:
            pygame.draw.circle(screen, self.TEXT, center, self._radius + 3, 2)
        if not zone.zone_type.passable:
            r = self._radius * 0.6
            x, y = center
            pygame.draw.line(screen, (200, 60, 60), (x - r, y - r),
                             (x + r, y + r), 3)
            pygame.draw.line(screen, (200, 60, 60), (x - r, y + r),
                             (x + r, y - r), 3)
        elif zone.unlimited:
            self._text(screen, str(count), center, self._contrast(color))
        else:
            self._text(screen, f"{count}/{zone.max_drones}", center,
                       self._contrast(color))
        label = self._label_font.render(zone.name, True, self.TEXT)
        screen.blit(label, self._labels[zone.name])

    def _draw_drone(self, screen: pygame.Surface, drone: Drone) -> None:
        """A small numbered dot sliding between this turn and the next"""
        if self._turn >= drone.arrival_turn:
            return  # delivered, it's counted in the end zone instead
        here = drone.position_at(self._turn)
        there = drone.position_at(self._turn + 1)
        start = self._network.start.name
        if here.zone == start and there.zone == start:
            return  # still waiting, it's counted in the start zone
        a, b = self._point(here), self._point(there)
        t = self._progress
        x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
        # spread drones a bit so two in the same zone don't overlap
        angle = drone.drone_id * 2.4
        spread = self._radius * 0.5
        x, y = x + math.cos(angle) * spread, y + math.sin(angle) * spread
        size = max(7, int(self._radius * 0.55))
        pygame.draw.circle(screen, self.DRONE, (x, y), size)
        pygame.draw.circle(screen, self.BACKGROUND, (x, y), size, 2)
        self._text(screen, str(drone.drone_id), (x, y), self.BACKGROUND)

    def _draw_hud(self, screen: pygame.Surface) -> None:
        """Bottom bar with the turn, the current moves and the controls"""
        width, height = screen.get_size()
        top = height - self.HUD_HEIGHT
        pygame.draw.rect(screen, self.HUD, (0, top, width, self.HUD_HEIGHT))
        shown = self._turn + (1 if self._progress > 0 else 0)
        delivered = sum(1 for d in self._sim.drones
                        if d.arrival_turn <= self._turn)
        status = "PAUSED" if self._paused else f"{1 / self._turn_seconds:.1f}"
        status += " turns/s" if not self._paused else ""
        header = (f"Turn {shown}/{self._sim.total_turns}    "
                  f"Delivered {delivered}/{len(self._sim.drones)}    "
                  f"{status}")
        self._text(screen, header, (16, top + 18), self.TEXT,
                   big=True, centered=False)
        moves = self._sim.line_at(shown) if shown > 0 else "(start)"
        self._text(screen, moves[:180], (16, top + 46), self.DRONE,
                   centered=False)
        controls = ("SPACE pause   LEFT/RIGHT step   UP/DOWN speed   "
                    "R restart   ESC quit")
        self._text(screen, controls, (16, top + 70), self.LINK,
                   centered=False)

    def _text(self, screen: pygame.Surface, text: str, at: Point,
              color: pygame.Color | tuple[int, int, int],
              big: bool = False, centered: bool = True) -> None:
        """Render a bit of text, centered on `at` unless told otherwise"""
        font = self._big_font if big else self._font
        surface = font.render(text, True, color)
        rect = surface.get_rect()
        if centered:
            rect.center = (int(at[0]), int(at[1]))
        else:
            rect.midleft = (int(at[0]), int(at[1]))
        screen.blit(surface, rect)

    # ---- labels ----

    def _place_labels(self) -> dict[str, pygame.Rect]:
        """Put each name below its zone, or above/right/left if that's taken"""
        r = self._radius
        taken: list[pygame.Rect] = []
        for name in self._network.zones:  # circles count as taken too
            x, y = self._zone_point(name)
            taken.append(pygame.Rect(x - r, y - r, 2 * r, 2 * r))
        placed: dict[str, pygame.Rect] = {}
        zones = sorted(self._network.zones.values(),
                       key=lambda zone: (zone.x, zone.y))
        for zone in zones:
            x, y = self._zone_point(zone.name)
            w, h = self._label_font.size(zone.name)
            options = [
                pygame.Rect(x - w / 2, y + r + 3, w, h),      # below
                pygame.Rect(x - w / 2, y - r - 3 - h, w, h),  # above
                pygame.Rect(x + r + 4, y - h / 2, w, h),      # right
                pygame.Rect(x - r - 4 - w, y - h / 2, w, h),  # left
            ]
            free = [rect for rect in options if rect.collidelist(taken) == -1]
            placed[zone.name] = free[0] if free else options[0]
            taken.append(placed[zone.name])
        return placed

    def _closest_pair(self) -> float:
        """Smallest distance between two zone centers, in pixels"""
        points = [self._zone_point(name) for name in self._network.zones]
        best = math.inf
        for i, a in enumerate(points):
            for b in points[i + 1:]:
                best = min(best, math.dist(a, b))
        return best if 0 < best < math.inf else 100.0

    # ---- helpers ----

    def _occupancy(self) -> dict[str, int]:
        """How many drones sit in each zone, switching halfway through"""
        turn = self._turn + (1 if self._progress >= 0.5 else 0)
        counts: dict[str, int] = {}
        for drone in self._sim.drones:
            pos = drone.position_at(turn)
            if pos.zone is not None:
                counts[pos.zone] = counts.get(pos.zone, 0) + 1
        return counts

    def _zone_color(self, zone: Zone) -> pygame.Color:
        """Turn the map's color name into a real color"""
        if not zone.zone_type.passable:
            return self.BLOCKED
        try:
            return pygame.Color(zone.color or "")
        except ValueError:  # no color, or a name pygame doesn't know
            return self.DEFAULT_ZONE

    @staticmethod
    def _contrast(color: pygame.Color) -> pygame.Color:
        """Black text on light colors, white text on dark ones"""
        light = 0.299 * color.r + 0.587 * color.g + 0.114 * color.b > 150
        return pygame.Color(0, 0, 0) if light else pygame.Color(255, 255, 255)
