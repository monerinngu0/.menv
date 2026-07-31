# kyopro

Download an AtCoder contest with the original command:

```bash
knew abc400
```

Create a site-independent contest without searching or downloading anything:

```bash
knew local-001 --manual --site local --problems a b c
cd local-001
```

`--problems` also accepts comma-separated labels. `--url` stores an optional
contest URL as metadata.

Add custom test cases interactively. End each input block with a line containing
only `.`:

```bash
ktest a --add-case
ktest a --add-case edge
```

Test data can instead be copied from files:

```bash
ktest a --add-case edge --input-file input.txt --output-file expected.txt
```

List or run all downloaded and custom cases:

```bash
ktest a --list-cases
ktest a
```
