# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.hooks.tcl_tk import tcltk_info

block_cipher = None

hiddenimports = [
    'psycopg2',
    'psycopg2._psycopg',
    'dotenv',
    'tkinter',
    '_tkinter',
    'win32com',
    'win32com.client',
    'win32print',
    'win32api',
    'pythoncom',
    'pywintypes',
    'UI.components.sidebar',
    'UI.components.autofill_center',
    'UI.components.autofill_center_runtime',
    'UI.components.analyticsPage',
    'UI.components.aiChatPage',
    'UI.components.summaryPanel',
    'UI.components.taskManager',
    'UI.components.resizablePane',
    'BE.src.cash_sheet_filler.main',
    'BE.src.cash_sheet_filler.infor_parser',
    'BE.src.cash_sheet_filler.tavlo_parser',
    'BE.src.cash_sheet_filler.grubhub_parser',
    'BE.src.cash_sheet_filler.excel_autofiller',
    'BE.src.cash_sheet_filler.base_parser',
    'BE.src.cash_sheet_filler.config',
    'BE.src.tender_break.autofill',
    'BE.src.tender_break.config',
    'BE.src.db.tendersdb_manager',
    'BE.src.ai_engine',
    'BE.src.updater',
    'BE.src.printer',
    'BE.src.path_helper',
    'BE.src.utils',
    'BE.src.cache',
]
hiddenimports = list(dict.fromkeys(
    hiddenimports
    + collect_submodules('BE')
    + collect_submodules('UI.components')
))

datas = [
    ('logo/chartwells.jfif', 'logo'),
    ('BE/src/cash_sheet_filler/cash_sheet_config.json', 'BE/src/cash_sheet_filler'),
    ('BE/src/tender_break/tender_config.json', 'BE/src/tender_break'),
    ('BE/src/cash_sheet_filler/cash_sheet_config.json', 'config_defaults'),
    ('BE/src/tender_break/tender_config.json', 'config_defaults'),
]
datas = [
    data for data in datas
    if Path(data[0]).exists() or data[0] != 'logo/chartwells.jfif'
]
datas += [
    (src, str(Path(dest).parent))
    for dest, src, _typecode in tcltk_info.data_files
]

excludes = ['tkinter.test', 'test', 'tests', 'pytest']

a = Analysis(
    ['UI/dashboard.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ChartwellsAutomation',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='ChartwellsAutomation',
)
