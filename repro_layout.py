"""
RÉPRODUCTION DU BUG — touches lues par le jeu vs touches documentées dans le README.

Méthode : on charge le fichier HTML RÉEL dans Chromium headless, on clique JOUER,
on maintient une touche pendant N frames, et on lit le déplacement réel de player.x.
Aucune réécriture du code : on teste le jeu tel qu'il est publié.
"""
import sys, json, pathlib
from playwright.sync_api import sync_playwright

HTML = pathlib.Path(__file__).parent / "space-shooter.html"
FRAMES_MS = 250  # ~15 frames à 60fps

# (touche, ce que le README promet)
CASES = [
    ("ArrowLeft", "gauche", "flèche gauche (bonus non documenté)"),
    ("d",         "droite", "D — documentée comme droite"),
    ("q",         "gauche", "Q — non documenté, fonctionne en AZERTY"),
    ("a",         "gauche", "A — DOCUMENTÉ dans le README comme gauche"),
    ("z",         "haut",   "Z — non documenté, fonctionne en AZERTY"),
    ("w",         "haut",   "W — haut sur clavier QWERTY"),
    ("s",         "bas",    "S — bas (commun aux deux dispositions)"),
    ("ArrowRight","droite", "flèche droite"),
]


def state(page):
    return page.evaluate("() => ({x: player.x, y: player.y, keys: Object.keys(keys)})")


def run():
    if not HTML.exists():
        sys.exit(f"FICHIER INTROUVABLE : {HTML}")

    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--mute-audio"])
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        page.goto(HTML.as_uri())
        page.wait_for_timeout(300)

        # prouver que le binding global est bien lisible → sinon la mesure est invalide
        probe = page.evaluate("() => typeof player")
        if probe != "object":
            browser.close()
            sys.exit(f"INSTRUMENTATION INVALIDE : typeof player = {probe}")

        for key, attendu, label in CASES:
            # partie neuve à chaque mesure pour repartir d'une position identique
            page.evaluate("""() => {
                try { startGame(); } catch(e) {}
                player.x = 640; player.y = 400; player.vx = 0; player.vy = 0;
                mouse.act = false;
                for (const k in keys) delete keys[k];
            }""")
            page.wait_for_timeout(60)
            before = state(page)

            page.keyboard.down(key)
            page.wait_for_timeout(60)
            # CONTRÔLE DÉCISIF : la touche est-elle bien enregistrée par le jeu ?
            recue = page.evaluate(f"() => Object.keys(keys).filter(k => keys[k] === true)")
            page.wait_for_timeout(FRAMES_MS - 60)
            after = state(page)
            page.keyboard.up(key)
            page.wait_for_timeout(60)

            dx = round(after["x"] - before["x"], 2)
            dy = round(after["y"] - before["y"], 2)
            moved = abs(dx) > 1 or abs(dy) > 1
            # le README promet un déplacement : on vérifie que le SENS correspond
            sens_ok = (
                (attendu == "gauche" and dx < -1)
                or (attendu == "droite" and dx > 1)
                or (attendu == "haut" and dy < -1)
                or (attendu == "bas" and dy > 1)
            )
            results.append({
                "touche": key, "attendu_README": attendu, "label": label,
                "touche_recue_par_le_jeu": recue,
                "dx": dx, "dy": dy, "bouge": moved, "sens_conforme": sens_ok,
            })

        browser.close()

    print(json.dumps({"erreurs_js": errors, "mesures": results}, indent=2, ensure_ascii=False))

    # verdict
    ko = [r for r in results if not r["sens_conforme"]]
    print("\n=== VERDICT ===")
    for r in results:
        print(f"  {'OK  ' if r['sens_conforme'] else 'ÉCHEC'}  {r['touche']:<10} "
              f"dx={r['dx']:>7} dy={r['dy']:>7}  {r['label']}")
    # une touche reçue par le jeu mais qui ne produit aucun déplacement = bug de logique
    ignorees = [r for r in results if r["touche_recue_par_le_jeu"] and not r["bouge"]]
    print(f"\nTouches REÇUES par le jeu mais IGNORÉES par la logique : "
          f"{[r['touche'] for r in ignorees]}")
    print(f"{len(ko)} touche(s) attendue(s) par le README ne déplacent pas le vaisseau.")
    sys.exit(0 if not ko else 1)


if __name__ == "__main__":
    run()
