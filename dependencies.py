"""
Wrapper on Pip to install required python modules
"""

import subprocess
import importlib


def resolve(dep):
    error = False
    output = b""
    cmd = ["python3", "-m", "pip", "install", dep, "--user"]

    try:
        output = subprocess.check_output(cmd, creationflags=subprocess.CREATE_NO_WINDOW)
    except subprocess.CalledProcessError:
        try:
            importlib.import_module(dep)
        except ModuleNotFoundError:
            error = True

    return [error, " ".join(cmd), output.decode("utf-8")]


def import_or_install(dep):
    try:
        importlib.import_module(dep)
        return [False, ""]
    except ModuleNotFoundError:
        return resolve(dep)
