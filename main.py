
import math
import sys
import time
import queue
import itertools
from dataclasses import dataclass

import pygame

from IvyClass import IvyAgent
from gestures import GestureRecognizer


# ============================================================
# CONFIGURATION
# ============================================================

WIDTH = 1100
HEIGHT = 720
FPS = 60


WHITE = (255, 255, 255)
BLACK = (30, 30, 30)
LIGHT_GRAY = (240, 242, 245)
GRAY = (150, 155, 165)
BLUE = (65, 125, 230)
GREEN = (50, 180, 110)
RED = (225, 75, 75)

COLORS = {
    "red": (230, 65, 65),
    "green": (50, 180, 100),
    "blue": (65, 125, 230),
    "gray": (120, 125, 135),
}

SHAPES = ["rectangle", "circle", "triangle", "diamond"]

CLICK_MAX_LENGTH = 6      # px: a shorter press/release path is a click, a longer one a stroke
GESTURE_END_DELAY = 0.6   # s without a new stroke before recognizing a (multi-stroke) gesture


# ============================================================
# DRAWING OBJECT
# ============================================================

@dataclass
class Shape:
    id: int
    shape_type: str
    color: str
    x: int
    y: int
    size: int = 70

    def describe(self):
        return f"{self.id}:{self.shape_type}:{self.color}"

    def contains(self, pos):
        px, py = pos

        # Test simple de sélection par boîte englobante
        return (
            self.x - self.size // 2 <= px <= self.x + self.size // 2
            and
            self.y - self.size // 2 <= py <= self.y + self.size // 2
        )

    def draw(self, surface):
        color = COLORS.get(self.color, BLUE)

        rect = pygame.Rect(
            self.x - self.size // 2,
            self.y - self.size // 2,
            self.size,
            self.size
        )

        if self.shape_type == "rectangle":
            pygame.draw.rect(surface, color, rect, border_radius=4)

        elif self.shape_type == "circle":
            pygame.draw.circle(
                surface, color, (self.x, self.y), self.size // 2
            )

        elif self.shape_type == "triangle":
            points = [
                (self.x, self.y - self.size // 2),
                (self.x - self.size // 2, self.y + self.size // 2),
                (self.x + self.size // 2, self.y + self.size // 2),
            ]
            pygame.draw.polygon(surface, color, points)

        elif self.shape_type == "diamond":
            points = [
                (self.x, self.y - self.size // 2),
                (self.x + self.size // 2, self.y),
                (self.x, self.y + self.size // 2),
                (self.x - self.size // 2, self.y),
            ]
            pygame.draw.polygon(surface, color, points)


# ============================================================
# WHITEBOARD
# ============================================================

class Whiteboard:

    TOOLBAR_HEIGHT = 105
    SIDEBAR_WIDTH = 250

    def __init__(self):
        pygame.init()

        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Multimodal Whiteboard - Ivy")

        self.clock = pygame.time.Clock()

        self.font = pygame.font.SysFont("Arial", 18)
        self.small_font = pygame.font.SysFont("Arial", 14)
        self.title_font = pygame.font.SysFont("Arial", 23, bold=True)

        self.shapes = []
        self.id_counter = itertools.count(1)

        self.recognizer = GestureRecognizer()
        self.current_stroke = None
        self.strokes = []
        self.gesture_deadline = 0.0

        self.fusion_state = "IDLE"
        self.fusion_text = "-"

        self.event_queue = queue.Queue()
        self.logs = []

        self.canvas = pygame.Rect(
            0,
            self.TOOLBAR_HEIGHT,
            WIDTH - self.SIDEBAR_WIDTH,
            HEIGHT - self.TOOLBAR_HEIGHT
        )

        # Agent Ivy indépendant du thread graphique
        self.ivy = IvyAgent(self.event_queue)

        self.log("Whiteboard ready")
        self.log(f"Ivy bus: {self.ivy.IVY_BUS}")

    # --------------------------------------------------------
    # SHAPE MANAGEMENT
    # --------------------------------------------------------

    def create_shape(self, shape_type, color, x, y):
        if shape_type not in SHAPES:
            self.log(f"Unknown shape: {shape_type}")
            return

        if color not in COLORS:
            self.log(f"Unknown color: {color}")
            return

        object_id = next(self.id_counter)

        shape = Shape(
            id=object_id,
            shape_type=shape_type,
            color=color,
            x=x,
            y=y
        )

        self.shapes.append(shape)

        self.log(
            f"Created #{object_id}: {shape_type} / {color}"
        )

        self.ivy.send(
            f"PALETTE_CREATED id={object_id} "
            f"shape={shape_type} color={color} x={x} y={y}"
        )

    def get_shape(self, object_id):
        shape = next(
            (s for s in self.shapes if s.id == object_id),
            None
        )

        if shape is None:
            self.log(f"Object #{object_id} not found")

        return shape

    def move_shape(self, object_id, x, y):
        shape = self.get_shape(object_id)

        if shape is None:
            return

        shape.x = x
        shape.y = y

        self.log(f"Moved #{object_id}")
        self.ivy.send(
            f"PALETTE_MOVED id={object_id} x={x} y={y}"
        )

    def delete_shape(self, object_id):
        shape = self.get_shape(object_id)

        if shape is None:
            return

        self.shapes.remove(shape)

        self.log(f"Deleted #{object_id}")
        self.ivy.send(f"PALETTE_DELETED id={object_id}")

    def recolor_shape(self, object_id, color):
        shape = self.get_shape(object_id)

        if shape is None or color not in COLORS:
            return

        shape.color = color

        self.log(f"Recolored #{object_id}: {color}")
        self.ivy.send(f"PALETTE_COLORED id={object_id} color={color}")

    def shapes_at(self, pos):
        # Formes sous le point, la plus récente (au-dessus) en premier
        return [s for s in reversed(self.shapes) if s.contains(pos)]

    # --------------------------------------------------------
    # IVY EVENTS
    # --------------------------------------------------------

    def process_ivy_events(self):
        while not self.event_queue.empty():
            event = self.event_queue.get()

            if event["type"] == "create":
                self.create_shape(
                    event["shape"],
                    event["color"],
                    event["x"],
                    event["y"]
                )

            elif event["type"] == "move":
                self.move_shape(
                    event["id"],
                    event["x"],
                    event["y"]
                )

            elif event["type"] == "delete":
                self.delete_shape(event["id"])

            elif event["type"] == "color":
                self.recolor_shape(event["id"], event["color"])

            elif event["type"] == "clear":
                self.shapes.clear()
                self.log("Clear command received from Ivy")

            elif event["type"] == "status":
                self.fusion_state = event["state"]
                self.fusion_text = event["text"]

    # --------------------------------------------------------
    # MOUSE : clic = désignation, tracé = geste
    # --------------------------------------------------------

    def handle_mouse_down(self, pos):
        if self.canvas.collidepoint(pos):
            self.current_stroke = [pos]

    def handle_mouse_motion(self, pos):
        if self.current_stroke is not None:
            self.current_stroke.append(pos)

    def handle_mouse_up(self):
        if self.current_stroke is None:
            return

        stroke = self.current_stroke
        self.current_stroke = None

        length = sum(math.dist(a, b) for a, b in zip(stroke, stroke[1:]))

        if length < CLICK_MAX_LENGTH:
            self.recognize_gesture()
            self.send_click(stroke[0])
        else:
            self.strokes.append(stroke)
            self.gesture_deadline = time.time() + GESTURE_END_DELAY

    def send_click(self, pos):
        x, y = pos
        objects = ",".join(s.describe() for s in self.shapes_at(pos)) or "none"

        self.log(f"Click {x},{y}")
        self.ivy.send(f"PALETTE_CLICK x={x} y={y} objects={objects}")

    def update_gesture(self):
        if (
            self.strokes
            and self.current_stroke is None
            and time.time() >= self.gesture_deadline
        ):
            self.recognize_gesture()

    def recognize_gesture(self):
        if not self.strokes:
            return

        strokes = self.strokes
        self.strokes = []

        result = self.recognizer.recognize(strokes)

        if result is None:
            self.log("Gesture not recognized")
            return

        name, score = result
        points = [p for stroke in strokes for p in stroke]
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        x = (min(xs) + max(xs)) // 2
        y = (min(ys) + max(ys)) // 2

        self.log(f"Gesture: {name} ({score:.2f})")
        self.ivy.send(f"GESTURE name={name} score={score:.2f} x={x} y={y}")

    # --------------------------------------------------------
    # DRAWING
    # --------------------------------------------------------

    def log(self, message):
        self.logs.append(message)
        self.logs = self.logs[-12:]

        print("[UI]", message)

    def draw_toolbar(self):
        pygame.draw.rect(
            self.screen,
            LIGHT_GRAY,
            (0, 0, WIDTH, self.TOOLBAR_HEIGHT)
        )

        title = self.title_font.render(
            "Multimodal Whiteboard",
            True,
            BLACK
        )
        self.screen.blit(title, (15, 12))

        state = self.font.render(
            f"Fusion : {self.fusion_state}",
            True,
            GREEN if self.fusion_state == "IDLE" else RED
        )
        self.screen.blit(state, (15, 48))

        text = self.font.render(self.fusion_text, True, BLACK)
        self.screen.blit(text, (15, 74))

    def draw_canvas(self):
        pygame.draw.rect(self.screen, WHITE, self.canvas)

        # Grille discrète
        for x in range(0, self.canvas.width, 25):
            pygame.draw.line(
                self.screen, (245, 245, 245),
                (x, self.canvas.top),
                (x, HEIGHT)
            )

        for y in range(self.canvas.top, HEIGHT, 25):
            pygame.draw.line(
                self.screen, (245, 245, 245),
                (0, y),
                (self.canvas.width, y)
            )

        for shape in self.shapes:
            shape.draw(self.screen)

        strokes = self.strokes + ([self.current_stroke] if self.current_stroke else [])
        for stroke in strokes:
            if len(stroke) > 1:
                pygame.draw.lines(self.screen, GRAY, False, stroke, 3)

    def draw_sidebar(self):
        x = WIDTH - self.SIDEBAR_WIDTH

        pygame.draw.rect(
            self.screen,
            LIGHT_GRAY,
            (x, 0, self.SIDEBAR_WIDTH, HEIGHT)
        )

        pygame.draw.line(
            self.screen,
            GRAY,
            (x, 0),
            (x, HEIGHT),
            2
        )

        title = self.title_font.render("Ivy Probe", True, BLACK)
        self.screen.blit(title, (x + 20, 20))

        status = self.small_font.render(
            "Connected | Port 2010",
            True,
            GREEN
        )
        self.screen.blit(status, (x + 20, 55))

        pygame.draw.line(
            self.screen, GRAY,
            (x + 15, 85), (WIDTH - 15, 85)
        )

        label = self.font.render("Event log", True, BLACK)
        self.screen.blit(label, (x + 20, 100))

        for i, message in enumerate(self.logs):
            text = self.small_font.render(
                message[:30],
                True,
                BLACK
            )
            self.screen.blit(text, (x + 20, 135 + i * 27))

        pygame.draw.line(
            self.screen, GRAY,
            (x + 15, 490), (WIDTH - 15, 490)
        )

        help_lines = [
            "Mouse:",
            "Click = designation (ici, ce...)",
            "Draw = gesture",
            "Gestures: rectangle, cercle,",
            "triangle, losange,",
            "flèche = déplacer, X = supprimer",
        ]

        for i, line in enumerate(help_lines):
            text = self.small_font.render(line, True, BLACK)
            self.screen.blit(text, (x + 20, 510 + i * 22))

    def draw(self):
        self.screen.fill(WHITE)

        self.draw_canvas()
        self.draw_toolbar()
        self.draw_sidebar()

        pygame.display.flip()

    # --------------------------------------------------------
    # MAIN LOOP
    # --------------------------------------------------------

    def run(self):
        running = True

        while running:
            self.clock.tick(FPS)

            self.process_ivy_events()

            for event in pygame.event.get():

                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        self.handle_mouse_down(event.pos)

                elif event.type == pygame.MOUSEMOTION:
                    self.handle_mouse_motion(event.pos)

                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1:
                        self.handle_mouse_up()

            self.update_gesture()
            self.draw()

        self.ivy.stop()
        pygame.quit()
        sys.exit()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    app = Whiteboard()
    app.run()