"""
Wrapper on Pip to install required python modules
"""

import subprocess
import importlib


def resolve(dep):
    module = None
    output = b""
    cmd = ["python3", "-m", "pip", "install", dep, "--user"]

    # Try to install module
    try:
        output = subprocess.check_output(cmd, creationflags=subprocess.CREATE_NO_WINDOW)
    except subprocess.CalledProcessError:
        pass

    # Even if process failed, try to import module
    try:
        module = importlib.import_module(dep)
    except ModuleNotFoundError:
        pass

    return [module, " ".join(cmd), output.decode("utf-8")]


def import_or_install(dep):
    try:
        return importlib.import_module(dep)
    except ModuleNotFoundError:
        return resolve(dep)[0]
