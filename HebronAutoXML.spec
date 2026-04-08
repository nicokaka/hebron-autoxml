# -*- mode: python ; coding: utf-8 -*-
import os
import sys
import customtkinter
from playwright._impl._driver import compute_driver_executable, get_driver_env

ctk_path = os.path.dirname(customtkinter.__file__)

# ── Localizar os binários do Playwright (Chromium / driver) ─────────────────────────────────
# O Playwright armazena o Chromium em %USERPROFILE%\AppData\Local\ms-playwright
# Incluiímos apenas o Chromium para conter o tamanho do dist.
# Caso prefira usar Edge (já instalado no Windows), remova o bloco datas_playwright
# e o portal_scraper.py já faz fallback automático para Edge.
pw_browsers_dir = os.path.join(
    os.path.expanduser("~"),
    "AppData", "Local", "ms-playwright"
)
datas_playwright = []
if os.path.isdir(pw_browsers_dir):
    # Inclui apenas o chromium-* para não explodir o instalador
    for entry in os.listdir(pw_browsers_dir):
        if entry.startswith("chromium"):
            src = os.path.join(pw_browsers_dir, entry)
            datas_playwright.append((src, f"ms-playwright/{entry}"))
            break  # só o primeiro chromium

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        (os.path.join(ctk_path, 'assets'), 'customtkinter/assets'),
        *datas_playwright,          # Chromium do Playwright (se instalado)
    ],
    hiddenimports=[
        'openpyxl',
        'openpyxl.cell._writer',
        'cryptography',
        'cryptography.hazmat.primitives.serialization.pkcs12',
        'requests',
        'urllib3',
        'lxml._elementpath',
        'lxml.etree',
        'plyer',
        'plyer.platforms.win.notification',
        # Playwright
        'playwright',
        'playwright.sync_api',
        'playwright._impl._driver',
        'playwright._impl._playwright',
        'playwright._impl._browser',
        'playwright._impl._page',
        'greenlet',
        'pyee',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['signxml'],   # removido — não é mais usado
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='HebronAutoXML',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='scripts/icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='HebronAutoXML',
)
