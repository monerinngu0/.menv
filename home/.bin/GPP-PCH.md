# gpp PCH cache

`gpp` automatically precompiles `<bits/stdc++.h>` for local C++ source
compilations and reuses the generated GCC precompiled header (PCH).

## Usage

```sh
gpp main.cpp -O2 -o main
gpp main.cpp -O2 -d -o main-debug
gpp --no-pch main.cpp -O2 -o main
GPP_NO_PCH=1 gpp main.cpp -O2 -o main
```

No source changes are needed. The standard library is force-included by
`gpp`; explicit `#include <bits/stdc++.h>` is still fine and should remain
in source intended for AtCoder submissions.

The first compile for a configuration generates the PCH and can be slower.
Later compiles reuse it. Cache entries live under
`${XDG_CACHE_HOME:-$HOME/.cache}/gpp-pch/`. Remove this directory to reclaim
disk space or if a compiler installation changes without its version changing.

Cache keys distinguish compiler executable path/version/target and the flags
that the wrapper tracks, including `-d`, `-std`, `-O`, `-D`, `-U`, `-I`,
`-m`, and `-f` options. The wrapper skips PCH for preprocessing-only invocations
and selected options whose effects are difficult to cache safely.

Only the standard library is in the PCH; `mone-library` and `ac-library`
remain ordinary includes, so changing them doesn't require rebuilding PCH.

PCH can consume hundreds of MB per variant. Use `--no-pch` for unusual
compiler invocations. GCC may also silently reject an incompatible PCH and
parse the regular header; `-H` shows `!` if the PCH was used.
