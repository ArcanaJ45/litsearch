# -*- mode: python ; coding: utf-8 -*-
# macOS 平台打包配置

a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['requests', 'models', 'api_client', 'query_builder',
                   'doi_validator', 'exporter', 'impact_factor',
                   'relevance_analyzer'],
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
    [],
    exclude_binaries=True,
    name='LitSearch',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    argv_emulation=True,
    target_arch='universal2',    # 同时支持 Intel 和 Apple Silicon
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name='LitSearch',
)

app = BUNDLE(
    coll,
    name='LitSearch文献检索.app',
    icon=None,
    bundle_identifier='com.arcanaj.litsearch',
    info_plist={
        'CFBundleName': 'LitSearch文献检索',
        'CFBundleDisplayName': 'LitSearch 文献检索',
        'CFBundleShortVersionString': '1.1.0',
        'CFBundleVersion': '1.1.0',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '10.15',
    },
)
