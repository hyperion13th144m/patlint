# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

ROOT = Path.cwd()


datas = [
    (str(ROOT / "words"), "words"),
    (str(ROOT / "units"), "units"),
    (
        str(ROOT / "src" / "patent_document_checker" / "report" / "templates"),
        "patent_document_checker/report/templates",
    ),
    (
        str(ROOT / "src" / "patent_document_checker" / "ui"),
        "patent_document_checker/ui",
    ),
]

hiddenimports = [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
]


a = Analysis(
    [str(ROOT / "src" / "patent_document_checker" / "server.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="patent-checker-api",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
