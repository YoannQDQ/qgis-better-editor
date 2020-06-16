""" Scan plugin folder for translations"""
import os
import contextlib

from pathlib import Path


@contextlib.contextmanager
def working_directory(path):
    """Changes working directory and returns to previous on exit."""
    prev_cwd = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev_cwd)


if __name__ == "__main__":
    with working_directory(Path(__file__).parent):
        PATHS = []
        for path in Path("..").rglob("*.py"):
            PATHS.append(f'"{path}"')

        os.system(
            f"pylupdate5 -verbose -noobsolete {' '.join(PATHS)} -ts ./BetterEditor_fr.ts ./BetterEditor_en.ts"
        )
