import os
from typing import Literal

DeploymentMode = Literal["desktop", "cloud"]


def get_deployment_mode() -> DeploymentMode:
    return "desktop" if os.environ.get("VAYBOOKS_DATA_DIR") else "cloud"


def is_desktop() -> bool:
    return get_deployment_mode() == "desktop"
