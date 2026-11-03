"""Multimodal fusion engine (Ivy agent).

Inputs : sra5 (speech), GESTURE / PALETTE_CLICK (palette)
Outputs: PALETTE_* commands, FUSION_STATUS, ppilot5 speech feedback
"""
import os
import queue
import time

from ivy.ivy import IvyServer

from fusion_data import COLOR_FR, SHAPE_FR, SHAPES, Click, FusionFrame

IVY_BUS = os.environ.get("IVY_BUS", "127.255.255.255:2010")
TTS_AGENT = os.environ.get("TTS_AGENT", "ppilot5")

CLICK_WINDOW = 2.0       # s: max delay between a click and the speech it completes
GLOBAL_TIMEOUT = 10.0     # s: inactivity before abandoning an incomplete command
DEFAULT_POSITION = (425, 412)  # canvas center of the palette
DEFAULT_COLOR = "gray"

IDLE = "IDLE"
WAIT_INFO = "WAIT_INFO"          # mandatory information missing (shape, object, destination...)
WAIT_CLICK = "WAIT_CLICK"        # a spoken deictic waits for its click
WAIT_COMPLETE = "WAIT_COMPLETE"  # executable, waiting briefly for optional color / position


def parse_sra5(parsed):
    """'action=create shape=circle color=red' -> [('action','create'), ...] (order kept)."""
    tokens = []
    for word in parsed.strip().strip("'\"").split():
        key, sep, value = word.partition("=")
        if sep:
            tokens.append((key, value))
    return tokens


def parse_objects(text):
    if text == "none":
        return []
    objects = []
    for item in text.split(","):
        object_id, shape, color = item.split(":")
        objects.append((int(object_id), shape, color))
    return objects


class FusionEngine(IvyServer):

    def __init__(self):
        super().__init__("FusionEngine")
        self.events = queue.Queue()  # Ivy callbacks run on Ivy threads: everything goes through this queue
        self.frame = FusionFrame()
        self.state = IDLE
        self.deadline = None
        self.clicks = []

        self.bind_msg(self.on_speech, r"^sra5 Parsed=(.*?) Confidence=([\d.,]+)")
        self.bind_msg(self.on_gesture, r"^GESTURE name=(\w+) score=([\d.]+) x=(\d+) y=(\d+)$")
        self.bind_msg(self.on_click, r"^PALETTE_CLICK x=(\d+) y=(\d+) objects=(\S+)$")
        self.start(IVY_BUS)
        print(f"[FUSION] connected to {IVY_BUS}")

    # ---------------- Ivy callbacks (Ivy threads) ----------------

    def on_speech(self, agent, parsed, confidence):
        tokens = parse_sra5(parsed)
        if tokens:
            self.events.put(("speech", tokens))

    def on_gesture(self, agent, name, score, x, y):
        self.events.put(("gesture", (name, int(x), int(y))))

    def on_click(self, agent, x, y, objects):
        self.events.put(("click", Click(int(x), int(y), parse_objects(objects), time.time())))

    # ---------------- main loop ----------------

    def run(self):
        self.publish_status()
        try:
            while True:
                try:
                    kind, data = self.events.get(timeout=0.05)
                    print(f"[FUSION] {self.state} <- {kind} {data}")
                    getattr(self, f"handle_{kind}")(data)
                except queue.Empty:
                    pass
                if self.deadline is not None and time.time() >= self.deadline:
                    self.handle_timeout()
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    # ---------------- events ----------------

    def handle_speech(self, tokens):
        action = next((value for key, value in tokens if key == "action"), None)
        if action == "cancel":
            if self.state != IDLE:
                self.abort("Commande annulée.")
            return
        if action:
            self.start_command(action)
        elif self.state == IDLE:
            print("[FUSION] speech ignored: no command in progress")
            return
        self.frame.merge_speech([t for t in tokens if t[0] != "action"])
        self.consume_clicks()
        self.update_state()

    def handle_gesture(self, data):
        name, x, y = data
        if name in SHAPES:
            if self.frame.action not in (None, "create"):
                print("[FUSION] shape gesture ignored during", self.frame.action)
                return
            if self.frame.action is None or self.frame.shape is not None:
                self.start_command("create")
            self.frame.merge_gesture(name, x, y)
        elif name in ("move", "delete"):
            self.start_command(name)
        else:
            return
        self.consume_clicks()
        self.update_state()

    def handle_click(self, click):
        if self.clicks and click.t - self.clicks[-1].t > CLICK_WINDOW:
            self.clicks.clear()
        self.clicks.append(click)
        if self.state != IDLE:
            self.consume_clicks()
            self.update_state()

    def handle_timeout(self):
        if self.state == WAIT_COMPLETE:
            self.execute()
        elif self.state == WAIT_CLICK:
            self.abort("Je n'ai pas reçu de désignation, commande annulée.")
        elif self.state == WAIT_INFO:
            self.abort("Commande incomplète, annulée.")

    # ---------------- fusion ----------------

    def start_command(self, action):
        if self.state == WAIT_COMPLETE:
            self.execute()
        elif self.state != IDLE:
            self.abort("Commande précédente abandonnée.")
        self.frame.reset()
        self.frame.action = action

    def consume_clicks(self):
        """Match buffered clicks (made before or after the speech) with pending deictics, in order."""
        if self.clicks and time.time() - self.clicks[-1].t > CLICK_WINDOW:
            self.clicks.clear()
        if not self.frame.pending:
            return
        self.clicks = self.clicks[-len(self.frame.pending):]
        while self.clicks and self.frame.pending:
            error = self.frame.resolve(self.clicks.pop(0))
            if error:
                self.say(error)

    def update_state(self):
        frame = self.frame
        now = time.time()
        if frame.action is None:
            self.state, self.deadline = IDLE, None
        elif frame.pending:
            self.state, self.deadline = WAIT_CLICK, now + CLICK_WINDOW
        elif frame.missing():
            self.state, self.deadline = WAIT_INFO, now + GLOBAL_TIMEOUT
        elif frame.has_optional_left():
            self.state, self.deadline = WAIT_COMPLETE, now + CLICK_WINDOW
        else:
            self.execute()
            return
        self.publish_status()

    def execute(self):
        frame = self.frame
        if frame.action == "create":
            x, y = frame.position or frame.gesture_position or DEFAULT_POSITION
            color = frame.color or DEFAULT_COLOR
            self.send_msg(f"PALETTE_CREATE shape={frame.shape} color={color} x={x} y={y}")
            self.say(f"{SHAPE_FR[frame.shape]} {COLOR_FR[color]} dessinee.")
        elif frame.action == "move":
            x, y = frame.position
            self.send_msg(f"PALETTE_MOVE id={frame.object_id} x={x} y={y}")
            self.say("Forme a ete deplacee.")
        elif frame.action == "delete":
            self.send_msg(f"PALETTE_DELETE id={frame.object_id}")
            self.say("Forme supprimee.")
        elif frame.action == "recolor":
            self.send_msg(f"PALETTE_COLOR id={frame.object_id} color={frame.color}")
            self.say(f"Forme coloriee en {COLOR_FR[frame.color]}.")
        self.reset()

    def abort(self, message):
        self.say(message)
        self.reset()

    def reset(self):
        self.frame.reset()
        self.state, self.deadline = IDLE, None
        self.publish_status()

    # ---------------- outputs ----------------

    def say(self, text):
        print(f"[FUSION] say: {text}")
        self.send_msg(f'{TTS_AGENT} Say="{text}"')

    def publish_status(self):
        self.send_msg(f"FUSION_STATUS state={self.state} text={self.frame.describe()}")


if __name__ == "__main__":
    FusionEngine().run()
