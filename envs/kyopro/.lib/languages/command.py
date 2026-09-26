from __future__ import annotations

from pathlib import Path


class CommandError(Exception):
    pass


def render_command(
    template: tuple[str, ...],
    *,
    source: Path | None = None,
    output: Path | None = None,
) -> tuple[str, ...]:
    if not template:
        raise CommandError(
            "command must not be empty"
        )

    values = {
        "source": (
            str(source.resolve())
            if source is not None
            else None
        ),
        "output": (
            str(output.resolve())
            if output is not None
            else None
        ),
    }

    command: list[str] = []

    for argument in template:
        try:
            rendered = argument.format_map(
                _CommandValues(values)
            )
        except KeyError as error:
            raise CommandError(
                f"unknown command placeholder: "
                f"{error.args[0]}"
            ) from error

        command.append(rendered)

    return tuple(command)


class _CommandValues(dict[str, str | None]):
    def __getitem__(
        self,
        key: str,
    ) -> str:
        try:
            value = super().__getitem__(key)
        except KeyError:
            raise

        if value is None:
            raise CommandError(
                f"command placeholder "
                f"{{{key}}} is unavailable"
            )

        return value