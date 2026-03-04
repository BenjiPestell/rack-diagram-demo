# Debug spec — identical to RackDesigner.spec but with console=True
import os, sys
from PyInstaller.building.build_main import Analysis, PYZ, EXE

block_cipher = None

src_dir = os.path.join(os.getcwd(), 'src')
src_datas = [
    (os.path.join(src_dir, f), '.')
    for f in os.listdir(src_dir)
    if f.endswith('.py')
]

a = Analysis(
    ['server.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('rack_designer.html',  '.'),
        ('rack_inspector.html', '.'),
    ] + src_datas,
    hiddenimports=[
        'flask', 'werkzeug', 'werkzeug.serving', 'werkzeug.routing',
        'werkzeug.exceptions', 'jinja2', 'click', 'yaml',
        'qrcode', 'qrcode.image.pil', 'PIL', 'PIL.Image', 'PIL.ImageTk',
        'colorsys', 'csv', 'math', 'glob',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='RackDesigner_debug',
    debug=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,    # <-- keep terminal open to see errors
    onefile=True,
)
