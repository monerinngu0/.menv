from __future__ import annotations

from dataclasses import dataclass


class SubmissionError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class SubmissionLanguage:
    query: str
    id: str | None = None


SUBMISSION_LANGUAGES = {
    "atcoder": {
        "cpp": SubmissionLanguage(
            query="C++ 23",
        ),
        "python": SubmissionLanguage(
            query="CPython",
        ),
    },
}


def get_submission_language(
    site: str,
    language: str,
) -> SubmissionLanguage:
    site_languages = SUBMISSION_LANGUAGES.get(site)

    if site_languages is None:
        raise SubmissionError(
            f"submission site is not configured: "
            f"{site}"
        )

    result = site_languages.get(language)

    if result is None:
        raise SubmissionError(
            f"submission language is not configured: "
            f"{site}/{language}"
        )

    return result