from __future__ import annotations

from .atcoder import AtCoderSite
from .base import Site
from .codeforces import CodeforcesSite


SITES: dict[str, Site] = {
    "atcoder": AtCoderSite(),
    "codeforces": CodeforcesSite(),
}


def get_site(name: str) -> Site:
    try:
        return SITES[name]
    except KeyError:
        raise ValueError(
            f"unsupported site: {name}"
        )


def site_names() -> list[str]:
    return list(SITES)