from ivy.ivy import IvyServer
class IvyAgent(IvyServer):

    def __init__(self, event_queue,IVY_BUS = "127.255.255.255:2010"):
        self.IVY_BUS = IVY_BUS
        super().__init__("Palette")
        self.event_queue = event_queue

        # Commandes envoyées par le moteur de fusion
        self.bind_msg(
            self.on_create,
            r"^PALETTE_CREATE shape=(\w+) color=(\w+) x=(\d+) y=(\d+)$"
        )

        self.bind_msg(
            self.on_move,
            r"^PALETTE_MOVE id=(\d+) x=(\d+) y=(\d+)$"
        )

        self.bind_msg(
            self.on_delete,
            r"^PALETTE_DELETE id=(\d+)$"
        )

        self.bind_msg(
            self.on_color,
            r"^PALETTE_COLOR id=(\d+) color=(\w+)$"
        )

        self.bind_msg(
            self.on_clear,
            r"^PALETTE_CLEAR$"
        )

        self.bind_msg(
            self.on_status,
            r"^FUSION_STATUS state=(\w+) text=(.*)$"
        )

        # Connexion au bus Ivy
        self.start(IVY_BUS)

        print(f"[IVY] Connected to {IVY_BUS}")

    def on_create(self, agent, shape, color, x, y):
        self.event_queue.put({
            "type": "create",
            "shape": shape,
            "color": color,
            "x": int(x),
            "y": int(y),
        })

    def on_move(self, agent, object_id, x, y):
        self.event_queue.put({
            "type": "move",
            "id": int(object_id),
            "x": int(x),
            "y": int(y),
        })

    def on_delete(self, agent, object_id):
        self.event_queue.put({"type": "delete", "id": int(object_id)})

    def on_color(self, agent, object_id, color):
        self.event_queue.put({"type": "color", "id": int(object_id), "color": color})

    def on_clear(self, agent):
        self.event_queue.put({"type": "clear"})

    def on_status(self, agent, state, text):
        self.event_queue.put({"type": "status", "state": state, "text": text})

    def send(self, message):
        self.send_msg(message)
        print(f"[IVY TX] {message}")
