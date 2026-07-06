from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from core import Router


def load_env_routes(menv_root: Path, router: Router) -> None:
    sys.path.insert(0, str(menv_root / ".lib"))

    from common import ok, ng  # noqa: E402

    envs_dir = menv_root / "envs"

    if not envs_dir.is_dir():
        return

    for routes_path in sorted(envs_dir.glob("*/server/routes.py")):
        env_name = routes_path.parents[1].name
        module_name = f"menv_env_{env_name}_routes"

        try:
            env_root = routes_path.parents[1]
            env_lib = env_root / ".lib"

            if env_lib.is_dir():
                sys.path.insert(0, str(env_lib))

            spec = importlib.util.spec_from_file_location(module_name, routes_path)

            if spec is None or spec.loader is None:
                raise RuntimeError("failed to create module spec")

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            register = getattr(module, "register", None)

            if register is None:
                continue

            register(router)
            ok(f"route loaded: {env_name}")

        except Exception as e:
            ng(f"route load failed: {env_name}: {e}")