import math

import dollarN as dN

MIN_SCORE = 0.3


def _closed_variants(vertices):
    """Every start vertex and both directions of a closed polygon, as one-stroke templates."""
    variants = []
    for path in (vertices, vertices[::-1]):
        for i in range(len(path)):
            loop = path[i:] + path[:i]
            variants.append([loop + [loop[0]]])
    return variants


def _rotate(strokes, angle):
    c, s = math.cos(angle), math.sin(angle)
    return [[[x * c - y * s, x * s + y * c] for x, y in stroke] for stroke in strokes]


def _scaled(vertices, sy):
    return [[x, y * sy] for x, y in vertices]


RECTANGLE = [[0., 0.], [5., 0.], [5., 5.], [0., 5.]]
TRIANGLE = [[2.5, 5.], [0., 0.], [5., 0.]]
DIAMOND = [[2.5, 5.], [5., 2.5], [2.5, 0.], [0., 2.5]]
CIRCLE = [[2.5 + 2.5 * math.cos(2 * math.pi * k / 16),
           2.5 + 2.5 * math.sin(2 * math.pi * k / 16)] for k in range(16)]
ARROWS = [[[[0., 0.], [6., 0.]], [[6. - h, h], [6., 0.], [6. - h, -h]]] for h in (0.4, 0.8, 1.5)]
CROSS = [[[0., 0.], [5., 5.]], [[0., 5.], [5., 0.]]]
# Height ratios: shapes are rotated before being normalized, so the aspect ratio matters
ASPECTS = (0.6, 1.0, 1.6)


class GestureRecognizer:
    """$N recognizer: shapes (create), arrow (move), cross (delete)."""

    def __init__(self):
        self.r = dN.recognizer()
        # In dollarN, True means "keep the drawn orientation" (needed to tell rectangle from diamond).
        # Must be set before adding templates.
        self.r.set_rotation_invariance(True)
        self.r.set_same_nb_strokes(False)

        for name, vertices in (("rectangle", RECTANGLE), ("triangle", TRIANGLE),
                               ("diamond", DIAMOND), ("circle", CIRCLE)):
            for aspect in ASPECTS:
                for template in _closed_variants(_scaled(vertices, aspect)):
                    self.r.add_gesture(name, template)

        for arrow in ARROWS:
            for k in range(4):
                self.r.add_gesture("move", _rotate(arrow, k * math.pi / 2))
        self.r.add_gesture("delete", CROSS)

    def recognize(self, strokes):
        """strokes in screen coordinates (y down). Returns (name, score) or None."""
        flipped = [[[float(x), float(-y)] for x, y in stroke] for stroke in strokes]
        try:
            result = self.r.recognize(flipped)
        except (IndexError, ValueError, ZeroDivisionError):
            # dollarN can fail on degenerate input (too few / identical points)
            return None
        if not result["name"] or result["value"] < MIN_SCORE:
            return None
        return result["name"], float(result["value"])
