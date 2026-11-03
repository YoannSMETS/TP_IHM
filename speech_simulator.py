"""Speech simulator: buttons sending the same Ivy messages as sra5."""
import itertools
import os
import tkinter as tk

from ivy.ivy import IvyServer

IVY_BUS = os.environ.get("IVY_BUS", "127.255.255.255:2010")

SECTIONS = {
    "Commandes": [
        ("créer", "action=create"),
        ("créer un rectangle", "action=create shape=rectangle"),
        ("créer un cercle rouge", "action=create shape=circle color=red"),
        ("créer un triangle ici", "action=create shape=triangle position=here"),
        ("créer un losange de cette couleur", "action=create shape=diamond color=this"),
        ("créer un rectangle ici de cette couleur", "action=create shape=rectangle position=here color=this"),
        ("créer un cercle bleu ici", "action=create shape=circle color=blue position=here"),
        ("déplacer", "action=move"),
        ("déplacer cet objet ici", "action=move select=this position=here"),
        ("déplacer ce rectangle ici", "action=move select=this shape=rectangle position=here"),
        ("déplacer ce rectangle rouge ici", "action=move select=this shape=rectangle color=red position=here"),
        ("supprimer cet objet", "action=delete select=this"),
        ("colorier cet objet en vert", "action=recolor select=this color=green"),
        ("colorier ce cercle de cette couleur", "action=recolor select=this shape=circle color=this"),
        ("annuler", "action=cancel"),
    ],
    "Mots isolés": [
        ("rectangle", "shape=rectangle"),
        ("cercle", "shape=circle"),
        ("triangle", "shape=triangle"),
        ("losange", "shape=diamond"),
        ("rouge", "color=red"),
        ("vert", "color=green"),
        ("bleu", "color=blue"),
        ("de cette couleur", "color=this"),
        ("ici", "position=here"),
        ("cet objet", "select=this"),
        ("ce rectangle", "select=this shape=rectangle"),
        ("ce cercle", "select=this shape=circle"),
    ],
}


class SpeechSimulator(IvyServer):

    def __init__(self):
        super().__init__("sra5_simulator")
        self.counter = itertools.count(1)
        self.start(IVY_BUS)

    def send(self, parsed):
        self.send_msg(f"sra5 Parsed={parsed} Confidence=0,8 NP={next(self.counter)} Num_A=0")


def main():
    agent = SpeechSimulator()
    window = tk.Tk()
    window.title("Simulateur sra5")

    for column, (title, items) in enumerate(SECTIONS.items()):
        frame = tk.LabelFrame(window, text=title, padx=6, pady=6)
        frame.grid(row=0, column=column, sticky="n", padx=6, pady=6)
        for label, parsed in items:
            tk.Button(frame, text=label, anchor="w", width=36,
                      command=lambda p=parsed: agent.send(p)).pack(fill="x", pady=1)

    free = tk.Frame(window, padx=6, pady=6)
    free.grid(row=1, column=0, columnspan=2, sticky="we")
    tk.Label(free, text="Parsed =").pack(side="left")
    entry = tk.Entry(free, width=60)
    entry.pack(side="left", fill="x", expand=True)
    tk.Button(free, text="Envoyer", command=lambda: agent.send(entry.get())).pack(side="left")

    window.protocol("WM_DELETE_WINDOW", lambda: (agent.stop(), window.destroy()))
    window.mainloop()


if __name__ == "__main__":
    main()
