from pathlib import Path

from PyInstaller.utils.hooks import collect_all


project_dir = Path(SPECPATH)
model_dir = Path.home() / ".EasyOCR" / "model"
required_models = ("craft_mlt_25k.pth", "english_g2.pth")
missing_models = [name for name in required_models if not (model_dir / name).exists()]
if missing_models:
    raise SystemExit(
        "EasyOCR model dosyaları eksik: " + ", ".join(missing_models)
        + ". Geliştirme ortamında RF4Club Sync'i bir kez çalıştırıp modelleri indir."
    )

easyocr_datas, easyocr_binaries, easyocr_hiddenimports = collect_all("easyocr")
torchvision_datas, torchvision_binaries, torchvision_hiddenimports = collect_all("torchvision")
datas = easyocr_datas + torchvision_datas + [
    (str(model_dir / name), "easyocr-models") for name in required_models
]

a = Analysis(
    [str(project_dir / "rf4club_sync.py")],
    pathex=[str(project_dir)],
    binaries=easyocr_binaries + torchvision_binaries,
    datas=datas,
    hiddenimports=easyocr_hiddenimports + torchvision_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pandas", "matplotlib", "IPython", "notebook"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="RF4Club Sync",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="RF4Club Sync",
)
