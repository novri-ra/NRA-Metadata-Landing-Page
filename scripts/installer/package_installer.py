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
    
    if not os.path.exists(dist_dir):
        print(f"[ERROR] dist/NRA-Metadata not found. Run main build first!")
        return False
        
    print("[1/3] Packaging dist/NRA-Metadata into payload.dat...")
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
    
    print("[2/3] Compiling Standalone Installer via PyInstaller...")
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
    a.binaries,
    a.datas,
    [],
    name='Setup',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    uac_admin=True,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir='.',
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
'''
    spec_path = os.path.join(installer_dir, "installer.spec")
    with open(spec_path, "w", encoding="utf-8") as f:
        f.write(spec_content)
        
    res = subprocess.run([
        sys.executable, "-m", "PyInstaller",
        "--clean", "--noconfirm",
        spec_path
    ], cwd=installer_dir)
    
    if res.returncode == 0:
        # Move final exe to dist/NRA-Metadata-Installer/
        final_src = os.path.join(installer_dir, "dist", "Setup.exe")
        final_dst = os.path.join(final_out_dir, "Setup.exe")
        if os.path.exists(final_src):
            if os.path.exists(final_dst):
                os.remove(final_dst)
            shutil.move(final_src, final_dst)
            print(f"[3/3] [SUCCESS] Standalone Installer built at: {final_out_dir}")
            return True
            
    print("[ERROR] PyInstaller build failed.")
    return False

if __name__ == "__main__":
    package_installer()
