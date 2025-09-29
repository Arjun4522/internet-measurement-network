import sys
import subprocess
import importlib.util

from pydantic import BaseModel


def install_package(package_name: str):
    """Installs a Python package using pip."""
    try:
        _ = subprocess.check_call(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                package_name,
                "--break-system-packages",
            ]
        )
        print(f"Successfully installed {package_name}")
    except subprocess.CalledProcessError as e:
        print(f"Error installing {package_name}: {e}")


def check_package_availability(package_name: str):
    """Installs a Python package using pip."""

    if importlib.util.find_spec(package_name) is None:
        return False
    return True


def get_model_name(model: BaseModel) -> str:
    return ""