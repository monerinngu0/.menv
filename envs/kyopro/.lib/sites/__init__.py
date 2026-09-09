from __future__ import annotations

import importlib
from dataclasses import dataclass
from types import ModuleType


class SiteError(Exception):
    pass


class SubmissionUnavailable(SiteError):
    pass


@dataclass(frozen=True, slots=True)
class SubmitResult:
    success: bool
    returncode: int
    message: str = ""


SITE_MODULES = {
    "atcoder": "sites.atcoder",
    "local": "sites.local",
}


def get_site(name: str) -> ModuleType:
    module_name = SITE_MODULES.get(name)

    if module_name is None:
        raise SiteError(
            f"unsupported site: {name}"
        )

    try:
        module = importlib.import_module(
            module_name
        )
    except Exception as error:
        raise SiteError(
            f"failed to load site: {name}"
        ) from error

    if getattr(module, "NAME", None) != name:
        raise SiteError(
            f"invalid site module: {name}"
        )

    submit = getattr(
        module,
        "submit",
        None,
    )

    if not callable(submit):
        raise SiteError(
            f"submit() not found for site: {name}"
        )

    return module