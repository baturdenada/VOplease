import PyInstaller.__main__
import sys
from pathlib import Path

# Project paths
project_root = Path(__file__).parent
main_script = project_root / "main.py"
icon_path = project_root / "assets" / "icon.ico"  # You can add an icon later

# Create a simple icon if not exists
if not icon_path.exists():
    # Create a simple colored icon using PIL if available
    try:
        from PIL import Image, ImageDraw
        img = Image.new('RGBA', (256, 256), (30, 136, 229, 255))
        draw = ImageDraw.Draw(img)
        draw.text((80, 90), "VO", fill=(255, 255, 255, 255))
        img.save(icon_path, format='ICO', sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)])
        print(f"Created icon at {icon_path}")
    except ImportError:
        icon_path = None
        print("PIL not available, skipping icon creation")

args = [
    str(main_script),
    "--name=VOplease",
    "--onefile",
    "--windowed",
    "--clean",
    # CustomTkinter loads theme assets at runtime.
    "--collect-all=customtkinter",
]

if icon_path:
    args.append(f"--icon={icon_path}")

# Add version info
version_info = """
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(1, 0, 0, 0),
    prodvers=(1, 0, 0, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'VOplease'),
         StringStruct(u'FileDescription', u'VOplease - Text-to-Speech Dashboard'),
         StringStruct(u'FileVersion', u'1.0.0'),
         StringStruct(u'InternalName', u'VOplease'),
         StringStruct(u'LegalCopyright', u'MIT License'),
         StringStruct(u'OriginalFilename', u'VOplease.exe'),
         StringStruct(u'ProductName', u'VOplease'),
         StringStruct(u'ProductVersion', u'1.0.0')])
    ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""

import tempfile
with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
    f.write(version_info)
    version_file = f.name

args.append(f"--version-file={version_file}")

print("Building VOplease.exe...")
print("This may take a few minutes...")

try:
    PyInstaller.__main__.run(args)
    print("\nBuild complete!")
    print(f"Executable: {Path('dist') / 'VOplease.exe'}")
except Exception as e:
    print(f"\nBuild failed: {e}")
    sys.exit(1)
