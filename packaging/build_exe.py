"""Construit l'exécutable autonome : dist/MCSpeedrunPanel.exe (Windows) ou dist/MCSpeedrunPanel.

Prérequis : pip install pyinstaller. Utilisé par .github/workflows/release.yml.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import PyInstaller.__main__  # noqa: E402

from mcpanel.config import APP_NAME, APP_VERSION  # noqa: E402

BUILD = ROOT / "build"

# Métadonnées visibles dans Propriétés > Détails : un exe anonyme inquiète davantage
# Windows et les antivirus.
VERSION_INFO = """VSVersionInfo(
  ffi=FixedFileInfo(filevers={nums}, prodvers={nums}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040C04B0', [
      StringStruct('FileDescription', '{name}'),
      StringStruct('FileVersion', '{version}'),
      StringStruct('InternalName', 'MCSpeedrunPanel'),
      StringStruct('OriginalFilename', 'MCSpeedrunPanel.exe'),
      StringStruct('ProductName', '{name}'),
      StringStruct('ProductVersion', '{version}')])]),
    VarFileInfo([VarStruct('Translation', [1036, 1200])])
  ]
)
"""


def main() -> None:
    BUILD.mkdir(exist_ok=True)
    args = [
        str(ROOT / "packaging" / "launcher.py"),
        "--name", "MCSpeedrunPanel",
        "--onefile",
        "--console",          # la fenêtre affiche l'adresse du panel ; la fermer arrête tout
        "--noupx",            # exe compressé par UPX = faux positifs antivirus garantis
        "--clean", "--noconfirm",
        "--paths", str(ROOT),
        "--add-data", "%s%sweb" % (ROOT / "web", os.pathsep),
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(BUILD),
        "--specpath", str(BUILD),
    ]
    if sys.platform == "win32":
        nums = tuple(int(part) for part in APP_VERSION.split(".")) + (0,)
        version_file = BUILD / "version_info.txt"
        version_file.write_text(VERSION_INFO.format(nums=nums, name=APP_NAME, version=APP_VERSION),
                                encoding="utf-8")
        args += ["--version-file", str(version_file)]
    PyInstaller.__main__.run(args)


if __name__ == "__main__":
    main()
