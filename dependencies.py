"""
Wrapper on Pip to install required python modules
"""

import subprocess
import importlib


def check_module(module):
    try:
        importlib.import_module(module)
    except ModuleNotFoundError:
        return False
    return True


def check_pip():
    return check_module("pip")


def install(dep):
    module = None

    if not check_pip():
        return module

    cmd = ["python3", "-m", "pip", "install", dep, "--user"]

    # Prevents the call to pip from spawning an console on Windows.
    try:
        subprocess.run(cmd, check=False, creationflags=subprocess.CREATE_NO_WINDOW)
    except (AttributeError, TypeError):
        subprocess.run(cmd, check=False)

    # Even if process failed, try to import module
    try:
        module = importlib.import_module(dep)
    except ModuleNotFoundError:
        pass

    return module


def import_or_install(dep):
    try:
        return importlib.import_module(dep)
    except ModuleNotFoundError:
        return install(dep)
