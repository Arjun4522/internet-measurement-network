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
    return camel_to_snake(model.__name__)

import re

def camel_to_snake(name):
    """
    Converts a camel case string to a snake case string.

    Args:
        name (str): The input string in camel case.

    Returns:
        str: The converted string in snake case.
    """
    # Use a regular expression to find uppercase letters that are not at the beginning of the string
    # and insert an underscore before them.
    # Then convert the entire string to lowercase.
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()