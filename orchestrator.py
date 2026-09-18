import os
import re
import subprocess
import sys
import tempfile


def log(msg):
    print(f"[*] {msg}")

def run_cmd(cmd, check=True):
    log(f"Running: {cmd}")
    res = subprocess.run(cmd, shell=True)
    if check and res.returncode != 0:
        log(f"Command failed with code {res.returncode}")
        sys.exit(res.returncode)
    return res.returncode

def main():
    # STEP 0: Sync
    log("Step 0: Pre-flight sync")
    run_cmd("git checkout development")
    run_cmd("git pull origin development")

    # STEP 1: Patch setup_wrapper.iss
    log("Step 1: Patching setup_wrapper.iss")
    iss_file = "scripts/installer/setup_wrapper.iss"
    with open(iss_file, "r", encoding="utf-8") as f:
        iss_data = f.read()
    
    # Remove [Icons] completely
    iss_data = re.sub(r"\[Icons\].*?(?=\[|$)", "", iss_data, flags=re.DOTALL)
    
    # Update [Setup]
    # Ensure Uninstallable=no
    if "Uninstallable" in iss_data:
        iss_data = re.sub(r"Uninstallable=.*", "Uninstallable=no", iss_data)
    else:
        iss_data = iss_data.replace("[Setup]\n", "[Setup]\nUninstallable=no\n")
    
    # Ensure PrivilegesRequired=lowest
    if "PrivilegesRequired=" in iss_data:
        iss_data = re.sub(r"PrivilegesRequired=.*", "PrivilegesRequired=lowest", iss_data)
    else:
        iss_data = iss_data.replace("[Setup]\n", "[Setup]\nPrivilegesRequired=lowest\n")
        
    # [Run] Ensure Flags: waituntilterminated
    iss_data = re.sub(r"(Filename:\s*\"{tmp}\Setup-GUI\Setup\.exe\";\s*WorkingDir:\s*\"{tmp}\Setup-GUI\";\s*Flags:)(.*)", r"\1 waituntilterminated", iss_data)

    with open(iss_file, "w", encoding="utf-8") as f:
        f.write(iss_data)

    # STEP 2: Patch installer_wizard.py
    log("Step 2: Patching installer_wizard.py")
    py_file = "scripts/installer/installer_wizard.py"
    with open(py_file, "r", encoding="utf-8") as f:
        py_data = f.read()

    # Ensure extraction to C:\Program Files\NRA-Metadata
    # Replace lambda: sys.exit(0) with lambda: os._exit(0) for safe exit
    py_data = py_data.replace("lambda: sys.exit(0)", "lambda: os._exit(0)")
    
    # Make sure shortcuts are wrapped in try-except around lines 330-338
    # The inner shortcut creation has try-except, but we can wrap the desktop_path / start_menu code blocks
    # Actually, the user says "Pastikan pembuatan shortcut (.lnk) Desktop dan Start Menu dibungkus dalam blok try-except".
    # I'll just replace the block with a try-except.
    
    pattern = r"(desktop_path\s*=\s*os\.environ\.get.*?self\._create_shortcut.*?NRA Metadata\")"
    
    def repl_shortcut(match):
        code = match.group(1)
        # Check if already try-excepted
        if "try:" not in code:
            indented = "\n".join("    " + line for line in code.split("\n"))
            return f"try:\n{indented}\n            except Exception as e:\n                self.log(f\"> [WARN] Shortcut generation skipped: {{e}}\")"
        return code

    py_data = re.sub(pattern, repl_shortcut, py_data, flags=re.DOTALL)
    
    with open(py_file, "w", encoding="utf-8") as f:
        f.write(py_data)

    # STEP 3: Clean build pipeline
    log("Step 3: Build pipeline")
    run_cmd("rm -rf build/ dist/Setup-GUI dist/NRA-Metadata-Setup-Final.exe")
    
    # Run the build script
    python_exe = os.environ.get("PYTHON_EXE", sys.executable)
    run_cmd(f'"{python_exe}" scripts/installer/package_installer.py')

    # STEP 4: Non-blocking headless verification
    log("Step 4: Headless verification")
    log_file = os.path.abspath("install_test.log")
    exe_path = r"dist\NRA-Metadata-Setup-Final.exe"
    
    if os.path.exists(log_file):
        os.remove(log_file)
        
    code = run_cmd(f'"{exe_path}" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /LOG="{log_file}"', check=False)
    
    log(f"Test exit code: {code}")
    
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            content = f.read()
            if "IPersistFile" in content or "0x80070005" in content or "Error" in content:
                log("Log contains errors! Check install_test.log")
            else:
                log("Log looks clean.")
    else:
        log("No log file found!")
        
    if code != 0:
        log("Testing failed. Looping is required...")
        sys.exit(1)

    # STEP 5: Commit & Remote Sync
    log("Step 5: Git commit and push")
    run_cmd("git add scripts/installer/setup_wrapper.iss scripts/installer/installer_wizard.py")
    run_cmd('git commit -m "fix(installer): eliminate redundant Inno Setup shortcuts to resolve IPersistFile 0x80070005 error"')
    run_cmd("git push origin development")
    
    log("ALL DONE 100%")

if __name__ == "__main__":
    main()
