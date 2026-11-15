"""CI Windows : un processus lancé par le panel doit mourir quand le panel meurt brutalement.

Simule la fenêtre fermée d'un clic sur X : un « panel » lance un faux serveur, le rattache
au job (instance.attach_to_kill_job), puis meurt sans rien arrêter.
"""
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

if sys.argv[1:] == ["panel"]:
    sys.path.insert(0, str(ROOT))
    from mcpanel.instance import attach_to_kill_job

    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(120)"],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=0x08000000 | 0x00000200,  # mêmes drapeaux que les serveurs Minecraft
    )
    print(child.pid, attach_to_kill_job(child.pid), flush=True)
    os._exit(0)  # mort brutale, aucun nettoyage

out = subprocess.run([sys.executable, __file__, "panel"], capture_output=True, text=True, timeout=60)
pid, attached = int(out.stdout.split()[0]), out.stdout.split()[1] == "True"
time.sleep(2)
alive = str(pid) in subprocess.run(["tasklist", "/FI", "PID eq %d" % pid], capture_output=True, text=True).stdout
print("rattaché au job : %s | encore vivant après la mort du panel : %s" % (attached, alive))
sys.exit(0 if attached and not alive else 1)
