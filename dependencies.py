"""
Wrapper on Pip to install required python modules
"""

import subprocess
import importlib


def check_module(module, min_version=""):
    try:
        m = importlib.import_module(module)
        if min_version and not check_minimum_version(m.__version__, min_version):
            return False
    except ModuleNotFoundError:
        return False
    return True


def check_pip():
    return check_module("pip")


def check_minimum_version(module_version, min_version):
    try:
        from packaging import version

        return version.parse(module_version) >= version.parse(min_version)
    except ModuleNotFoundError:
        return module_version >= min_version


def install(dep, upgrade=False):
    module = None
    module_version = ""

    if not check_pip():
        return module, module_version

    cmd = ["python3", "-m", "pip", "install", dep, "--user"]
    if upgrade:
        cmd.append("--upgrade")

    # Prevents the call to pip from spawning an console on Windows.
    try:
        subprocess.run(cmd, check=False, creationflags=subprocess.CREATE_NO_WINDOW)
    except (AttributeError, TypeError):
        subprocess.run(cmd, check=False)

    # Even if process failed, try to import module
    try:
        module = importlib.import_module(dep)
        module_version = module.__version__
    except ModuleNotFoundError:
        pass

    return module, module_version


def import_or_install(dep):
    try:
        module = importlib.import_module(dep)
        return module, module.__version__
    except ModuleNotFoundError:
        return install(dep)
