import os
import subprocess
import sys


if sys.platform.startswith("win"):
    default_path = r"C:\Program Files\Krita (x64)\bin\krita.exe"
elif sys.platform.startswith("darwin"):
    default_path = "/Applications/Krita.app/Contents/MacOS/krita"
else:
    default_path = "/usr/bin/krita"


krita_path = os.environ.get("KRITA_PATH", default_path)
cmd = [krita_path]
os.environ["KRITA_DEBUG"] = "1"
subprocess.Popen(cmd, env=os.environ)
