# Moteur de fusion multimodale — Rapport

> Squelette à compléter (captures d'écran, analyse, conclusion).

## 1. Introduction

Objectif : palette de dessin sans bouton, pilotée par la parole (sra5), des gestes ($N) dessinés sur la palette et le pointage souris, en s'inspirant de *Put That There* (Bolt, 1980).

## 2. Architecture

```mermaid
flowchart LR
    SRA[sra5<br/>reconnaissance vocale] -- "sra5 Parsed=... Confidence=..." --> F
    SIM[speech_simulator.py] -. "sra5 Parsed=..." .-> F
    P[Palette main.py<br/>+ $N gestures.py] -- "PALETTE_CLICK x y objects=..." --> F
    P -- "GESTURE name score x y" --> F
    F[Moteur de fusion<br/>fusion.py] -- "PALETTE_CREATE / MOVE / DELETE / COLOR" --> P
    F -- "FUSION_STATUS" --> P
    F -- "ppilot5 Say=..." --> TTS[ppilot5<br/>synthèse vocale]
```

### Protocole Ivy

| Émetteur | Message | Rôle |
|---|---|---|
| sra5 | `sra5 Parsed=action=create shape=circle color=red position=here Confidence=0,85 NP=1 Num_A=0` | résultat de reconnaissance |
| Palette | `PALETTE_CLICK x=<x> y=<y> objects=<id:forme:couleur,...\|none>` | pointage (objets sous le clic, du plus haut au plus bas) |
| Palette | `GESTURE name=<rectangle\|circle\|triangle\|diamond\|move\|delete> score=<s> x=<cx> y=<cy>` | geste reconnu (centre de la boîte englobante) |
| Fusion | `PALETTE_CREATE shape= color= x= y=` / `PALETTE_MOVE id= x= y=` / `PALETTE_DELETE id=` / `PALETTE_COLOR id= color=` | commandes |
| Fusion | `FUSION_STATUS state=<état> text=<résumé>` | retour visuel |
| Fusion | `ppilot5 Say=<texte>` | retour vocal |
| Palette | `PALETTE_CREATED / MOVED / DELETED / COLORED ...` | accusés d'exécution |

## 3. Grammaires

### Parole (`sra5/sra5/grammaire_parole.grxml`)

- Création : *créer / dessiner / tracer* [forme] [couleur \| « de cette couleur »] [« ici » \| « là »] (ordre couleur/position libre)
- Déplacement : *déplacer / bouger* [« cet objet » \| « ce » forme] [couleur] [« ici »]
- Suppression : *supprimer / effacer* [désignation] [couleur]
- Coloriage : *colorier / peindre* [désignation] [en] couleur \| « de cette couleur »
- Fragments isolés : forme, couleur, « ici », « cet objet », « ce rectangle », « annuler »

### Gestes (`gestures.py`, $N)

| Geste | Sens |
|---|---|
| rectangle, cercle, triangle, losange | forme à créer |
| flèche (2 traits, 4 directions) | action « déplacer » |
| croix X (2 traits) | action « supprimer » |

Distinction clic / geste sur la palette : un appui-relâché dont le tracé fait moins de 6 px est un **clic** ; sinon c'est un **trait**. Le geste (éventuellement multi-traits) est reconnu 0,6 s après le dernier trait.

## 4. Chronogrammes

Fenêtre d'association clic ↔ parole : **2 s** ; délai d'inactivité d'une commande incomplète : **5 s**.

### « Créer un rectangle ici rouge » + clic

```mermaid
sequenceDiagram
    participant U as Utilisateur
    participant P as Palette
    participant S as sra5
    participant F as Fusion
    U->>S: « créer un rectangle ici rouge »
    U->>P: clic (pendant « ici »)
    P->>F: PALETTE_CLICK x y
    Note over F: clic mis en tampon
    S->>F: Parsed=action=create shape=rectangle position=here color=red
    Note over F: déictique « ici » ← clic tamponné
    F->>P: PALETTE_CREATE rectangle red x y
    F->>U: ppilot5 « rectangle rouge créé »
```

### « Créer » + geste + « de cette couleur » + clic

```mermaid
sequenceDiagram
    participant U as Utilisateur
    participant P as Palette
    participant S as sra5
    participant F as Fusion
    U->>S: « créer »
    S->>F: Parsed=action=create
    Note over F: WAIT_INFO (forme manquante)
    U->>P: dessine un cercle
    P->>F: GESTURE name=circle x y
    Note over F: WAIT_COMPLETE (2 s pour options)
    U->>S: « de cette couleur »
    S->>F: Parsed=color=this
    Note over F: WAIT_CLICK
    U->>P: clic sur une forme verte
    P->>F: PALETTE_CLICK objects=3:rectangle:green
    F->>P: PALETTE_CREATE circle green (position du geste)
```

### « Déplacer ce rectangle rouge ici » + 2 clics

```mermaid
sequenceDiagram
    participant U as Utilisateur
    participant P as Palette
    participant S as sra5
    participant F as Fusion
    U->>P: clic 1 (sur « ce rectangle »)
    P->>F: PALETTE_CLICK objects=2:rectangle:red,1:rectangle:blue
    U->>P: clic 2 (sur « ici »)
    P->>F: PALETTE_CLICK objects=none
    S->>F: Parsed=action=move select=this shape=rectangle color=red position=here
    Note over F: objet ← clic 1 (filtré par forme+couleur)<br/>destination ← clic 2
    F->>P: PALETTE_MOVE id=2 x y
```

<!-- TODO : ajouter les variantes (clic avant / après la parole, geste flèche + « ce rectangle » + « ici »). -->

## 5. Contrôleur de dialogue

### Événements

| Événement | Source |
|---|---|
| `SPEECH(action?, forme?, couleur?, déictiques…)` | sra5 |
| `GESTURE(forme \| move \| delete, x, y)` | palette |
| `CLICK(x, y, objets)` | palette |
| `T_CLICK` (2 s) | timer |
| `T_GLOBAL` (5 s) | timer |
| `CANCEL` (« annuler ») | sra5 |

### Machine à états

```mermaid
stateDiagram-v2
    [*] --> IDLE
    IDLE --> WAIT_INFO: SPEECH(action) / GESTURE(move|delete)
    IDLE --> WAIT_COMPLETE: GESTURE(forme)
    IDLE --> IDLE: CLICK / mise en tampon
    WAIT_INFO --> WAIT_CLICK: SPEECH(déictique)
    WAIT_INFO --> WAIT_COMPLETE: info obligatoire reçue (création)
    WAIT_INFO --> IDLE: info obligatoire reçue / exécuter
    WAIT_INFO --> IDLE: T_GLOBAL / abandon
    WAIT_CLICK --> WAIT_CLICK: CLICK invalide / feedback vocal
    WAIT_CLICK --> WAIT_INFO: CLICK et info manquante
    WAIT_CLICK --> WAIT_COMPLETE: CLICK (création, options restantes)
    WAIT_CLICK --> IDLE: CLICK et commande complète / exécuter
    WAIT_CLICK --> IDLE: T_CLICK / abandon
    WAIT_COMPLETE --> WAIT_CLICK: SPEECH(déictique)
    WAIT_COMPLETE --> IDLE: T_CLICK / exécuter
    WAIT_COMPLETE --> IDLE: couleur et position connues / exécuter
    WAIT_INFO --> IDLE: CANCEL
    WAIT_CLICK --> IDLE: CANCEL
    WAIT_COMPLETE --> IDLE: CANCEL
```

Une nouvelle action (parole ou geste) en cours de commande : la commande courante est exécutée si elle est en `WAIT_COMPLETE`, sinon abandonnée.

### Matrice états / événements

| État \ Événement | SPEECH(action) | SPEECH(fragment) | GESTURE(forme) | GESTURE(move/delete) | CLICK | T_CLICK | T_GLOBAL | CANCEL |
|---|---|---|---|---|---|---|---|---|
| IDLE | nouvelle commande | ignoré | création | nouvelle commande | tampon | – | – | – |
| WAIT_INFO | abandon + nouvelle | fusion | fusion forme (si création) | abandon + nouvelle | tampon | – | abandon | abandon |
| WAIT_CLICK | abandon + nouvelle | fusion | fusion forme (si création) | abandon + nouvelle | résolution déictique | abandon | – | abandon |
| WAIT_COMPLETE | exécuter + nouvelle | fusion | exécuter + nouvelle création | exécuter + nouvelle | tampon | exécuter | – | abandon |

## 6. Conception logicielle

```mermaid
classDiagram
    class IvyServer
    class FusionEngine {
        state
        deadline
        clicks: list~Click~
        handle_speech(tokens)
        handle_gesture(data)
        handle_click(click)
        handle_timeout()
        consume_clicks()
        update_state()
        execute()
        abort(msg)
        say(text)
    }
    class FusionFrame {
        action
        shape
        color
        position
        object_id
        gesture_position
        pending: list
        reset()
        merge_speech(tokens)
        merge_gesture(shape, x, y)
        resolve(click)
        missing()
        has_optional_left()
    }
    class Click {
        x
        y
        objects
        t
    }
    class Whiteboard {
        shapes: list~Shape~
        strokes
        recognize_gesture()
        send_click(pos)
    }
    class Shape
    class IvyAgent
    class GestureRecognizer {
        recognize(strokes)
    }
    IvyServer <|-- FusionEngine
    IvyServer <|-- IvyAgent
    FusionEngine *-- FusionFrame
    FusionEngine o-- Click
    Whiteboard *-- IvyAgent
    Whiteboard *-- GestureRecognizer
    Whiteboard o-- Shape
```

`FusionFrame` est réinitialisée après chaque exécution, abandon ou annulation.

## 7. Exemples d'utilisation

<!-- TODO : captures d'écran -->

## 8. Limites et perspectives

<!-- TODO -->

## 9. Mode d'emploi

```
pip install -r requirements.txt
launch.bat        (sra5 réel)
launch.bat sim    (simulateur de parole)
```