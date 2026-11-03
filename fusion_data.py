from dataclasses import dataclass, field

SHAPES = ("rectangle", "circle", "triangle", "diamond")
COLORS = ("red", "green", "blue")

SHAPE_FR = {"rectangle": "rectangle", "circle": "cercle", "triangle": "triangle", "diamond": "losange"}
COLOR_FR = {"red": "rouge", "green": "vert", "blue": "bleu", "gray": "gris"}

# Deictic references that must be completed by a click on the palette
OBJECT, COLOR, POSITION = "object", "color", "position"


@dataclass
class Click:
    x: int
    y: int
    objects: list  # [(id, shape, color)], topmost first
    t: float


@dataclass
class FusionFrame:
    """Information gathered for the command in progress, filled as messages arrive."""

    action: str | None = None        # create | move | delete | recolor
    shape: str | None = None         # shape to create, or filter to find the object
    color: str | None = None         # color to apply, or filter (move / delete)
    position: tuple | None = None    # destination designated by a click
    object_id: int | None = None     # designated object
    gesture_position: tuple | None = None
    pending: list = field(default_factory=list)  # deictics waiting for a click, in spoken order

    def reset(self):
        self.__init__()

    def merge_speech(self, tokens):
        """tokens: ordered (key, value) pairs from sra5, without the action."""
        for key, value in tokens:
            if key == "shape" and value in SHAPES:
                self.shape = value
            elif key == "color":
                if value == "this":
                    self.pending.append(COLOR)
                elif value in COLORS:
                    self.color = value
            elif key == "position" and value == "here":
                self.pending.append(POSITION)
            elif key == "select" and value == "this":
                self.pending.append(OBJECT)

    def merge_gesture(self, shape, x, y):
        self.shape = shape
        self.gesture_position = (x, y)

    def resolve(self, click):
        """Assign a click to the first pending deictic. Returns an error message, or None."""
        kind = self.pending[0]
        if kind == POSITION:
            self.position = (click.x, click.y)
        elif kind == COLOR:
            if not click.objects:
                return "Il n'y a aucune forme à cet endroit."
            self.color = click.objects[0][2]
        elif kind == OBJECT:
            self.object_id = self._match(click.objects)
            if self.object_id is None:
                return f"Je ne trouve pas de {SHAPE_FR.get(self.shape, 'forme')} à cet endroit."
        self.pending.pop(0)
        return None

    def _match(self, objects):
        for object_id, shape, color in objects:
            if self.shape and shape != self.shape:
                continue
            # For recolor, color is the new color, not a filter
            if self.action in ("move", "delete") and self.color and color != self.color:
                continue
            return object_id
        return None

    def missing(self):
        """Mandatory information still unknown."""
        required = {
            "create": {"shape": self.shape},
            "move": {"object": self.object_id, "position": self.position},
            "delete": {"object": self.object_id},
            "recolor": {"object": self.object_id, "color": self.color},
        }.get(self.action, {})
        return [name for name, value in required.items() if value is None]

    def has_optional_left(self):
        """Only creation has optional parameters (color, position)."""
        return self.action == "create" and (self.color is None or self.position is None)

    def describe(self):
        if self.action is None:
            return "-"
        parts = [self.action]
        if self.shape:
            parts.append(SHAPE_FR[self.shape])
        if self.color:
            parts.append(COLOR_FR.get(self.color, self.color))
        if self.object_id is not None:
            parts.append(f"objet#{self.object_id}")
        if self.position:
            parts.append(f"@{self.position[0]},{self.position[1]}")
        if self.pending:
            parts.append("attend clic:" + "/".join(self.pending))
        return " ".join(parts)
