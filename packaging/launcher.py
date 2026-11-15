"""Point d'entrée de l'exécutable (PyInstaller) : python -m mcpanel, en double-clic."""
import sys
import traceback

from mcpanel.__main__ import main


def run() -> int:
    try:
        code = main()
    except SystemExit as exc:  # argparse, erreurs volontaires
        code = exc.code if isinstance(exc.code, int) else 1
    except Exception:  # noqa: BLE001 - tout afficher plutôt que fermer en silence
        traceback.print_exc()
        code = 1
    if code:
        # Lancé en double-clic, la fenêtre se fermerait avant qu'on puisse lire l'erreur.
        try:
            input("\nLe panel s'est arrêté sur une erreur (ci-dessus). Entrée pour fermer...")
        except (EOFError, KeyboardInterrupt):
            pass
    return code or 0


if __name__ == "__main__":
    sys.exit(run())
