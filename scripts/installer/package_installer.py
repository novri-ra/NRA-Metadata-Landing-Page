import os
import shutil
import zipfile
import subprocess
import sys

def package_installer():
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    dist_dir = os.path.join(root_dir, "dist", "NRA-Metadata")
    installer_dir = os.path.join(root_dir, "scripts", "installer")
    final_out_dir = os.path.join(root_dir, "dist", "NRA-Metadata-Installer")
    payload_dat = os.path.join(final_out_dir, "payload.dat")
    setup_gui_dir = os.path.join(root_dir, "dist", "Setup-GUI")
    
    if not os.path.exists(dist_dir):
        print(f"[ERROR] dist/NRA-Metadata not found. Run main build first!")
        return False
        
    print("[1/4] Packaging dist/NRA-Metadata into payload.dat...")
    os.makedirs(final_out_dir, exist_ok=True)
    if os.path.exists(payload_dat):
        os.remove(payload_dat)
        
    with zipfile.ZipFile(payload_dat, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(dist_dir):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, dist_dir)
                zf.write(full_path, rel_path)
                
    print(f"[SUCCESS] Payload ready: {os.path.getsize(payload_dat) / (1024*1024):.2f} MB")
    
    print("[2/4] Compiling Standalone Installer via PyInstaller (--onedir)...")
    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
a = Analysis(
    ['installer_wizard.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['customtkinter'],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Setup',
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
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Setup-GUI',
)
'''
    spec_path = os.path.join(installer_dir, "installer.spec")
    with open(spec_path, "w", encoding="utf-8") as f:
        f.write(spec_content)
        
    res = subprocess.run([
        sys.executable, "-m", "PyInstaller",
        "--clean", "--noconfirm",
        "--distpath", os.path.join(root_dir, "dist"),
        "--workpath", os.path.join(root_dir, "build"),
        spec_path
    ], cwd=installer_dir)
    
    if res.returncode == 0:
        print("[3/4] [SUCCESS] Standalone Installer built at dist/Setup-GUI")
        
        print("Membungkus dengan Inno Setup (Tunggu hingga selesai)...")
        final_exe = r"dist\NRA-Metadata-Setup-Final.exe"
        if os.path.exists(final_exe):
            os.remove(final_exe)
        
        iscc_path = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Inno Setup 6', 'ISCC.exe')
        if not os.path.exists(iscc_path):
            iscc_path = "iscc"
        
        try:
            subprocess.run([iscc_path, "scripts/installer/setup_wrapper.iss"], check=True)
            print("Build Inno Setup berhasil 100% tanpa corrupt!")
            return True
        except subprocess.CalledProcessError as e:
            print(f"FATAL ERROR: Build Inno Setup gagal di tengah jalan! {e}")
            return False
            
    print("[ERROR] PyInstaller build failed.")
    return False

if __name__ == "__main__":
    package_installer()
