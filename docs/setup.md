# 導入・更新

Ubuntu / Debian 系 Linux または WSL と Bash、Git を想定しています。
セットアップ本体は Python 3.11 以上の標準ライブラリで動作します。

## 初回導入

```bash
git clone https://github.com/monerinngu0/.menv.git "$HOME/.menv"
bash "$HOME/.menv/bootstrap.sh"
```

bootstrap は tomllib・venv・ensurepip が使える既存の Python を再利用します。
なければ、確認後に uv の公式インストーラーを取得し、専用の Python 3.13 を導入します。
ダウンロードには curl が必要です。システムの python3、既存のシェル設定は変更しません。
`MENV_PYTHON` で実行ファイルを指定することもできます。

`~/.bashrc` に追加します（clone先を変えた場合は MENV_ROOT を変更）。

```bash
export MENV_ROOT="$HOME/.menv"
export PATH="${XDG_DATA_HOME:-$HOME/.local/share}/menv/runtime/bin:$MENV_ROOT/.bin:$PATH"
me() { source "$MENV_ROOT/.bin/me" "$@"; }
```

新しい Bash を開きます。

```bash
setup list --local
setup init kyopro --dry-run
setup init kyopro
me kyopro
```

説明、オプション、作業場所、実際の引数列を表示し、`Proceed? [y/N]` の承認後に実行します。
旧 `mcheck` は廃止しました。旧 `.venv` と `.tools` は新しい定義でも再利用します。
導入履歴は自動移行しないので、既存ユーザーも `setup init kyopro` / `setup init song` を実行してください。
`setup update --all` の対象になるのは新しい init が成功したものだけです。

## C++ の準備

同梱の kyopro 定義は g++ の存在を確認します。必要に応じて自分で用意してください。
コンパイル設定は `envs/kyopro/.config` です。初期設定は gpp を使うため、次のように配置します。

```bash
mkdir -p "$HOME/.bin"
cp "$MENV_ROOT/home/.bin/gpp" "$HOME/.bin/gpp"
chmod +x "$HOME/.bin/gpp"
```

`~/.bashrc` に `export PATH="$HOME/.bin:$PATH"` を追加します。
gpp は C++23、最適化、ライブラリ検索パスを設定します。
`-d` で DEBUG と AddressSanitizer / UndefinedBehaviorSanitizer を有効にします。
詳細は [GPP-PCH.md](../home/.bin/GPP-PCH.md) と [競プロ設定](kyopro.md#提出用ソースの生成) を参照してください。
自作ライブラリと ACL は `~/library/mone-library`、`~/library/ac-library` に別途用意します。

gpp を使わない場合の設定例：

```toml
[cpp]
build_command = ["g++", "-std=gnu++23", "-O2", "{source}", "-o", "{output}"]
run_command = ["{output}"]
include_dirs = []
```

## 更新

```bash
git -C "$MENV_ROOT" pull --ff-only
setup update kyopro
setup update --all
```

リポジトリの更新とツールの更新は別操作です。更新対象、バージョン方針、上書き先は各TOMLに書きます。
init も update も指定された処理を実行します。既存バージョンの維持は各定義側の責任です。
実行中に失敗すると全体を停止します。成功済みの処理は取り消しません。
一括更新では全対象の計画を先に作り、一度の承認後に順番に実行します。

専用 Python を管理対象に含める場合は `setup init setup` を実行します。
`setup update setup` は専用runtimeのuvを取得し直し、Python 3.13の最新パッチへ更新してruntime内のpython3を切り替えます。
既存のenvのvenvは自動再作成しません。システムPythonを置き換える処理もありません。

## Remote レジストリ

```bash
setup list
setup search neovim
setup info remote:neovim
setup init remote:neovim --set version=0.11.7
setup update remote:neovim --set version=0.11.7
```

版番号は利用したい公開済みリリースを指定してください。同梱のNeovim定義は Linux x86_64 向けです。
版別ディレクトリに展開し、導入先の bin/nvim を切り替えます。PATHへの追加は手動です。

既定URLは `https://monerinngu0.github.io/.menv/` です。
レジストリを公開するには GitHub の Settings → Pages の Source を GitHub Actions にし、
`Publish setup registry` workflow を手動実行します。
この workflow は既存の Pages 公開先を置き換えるため、別用途の Pages がある場合は別レジストリを指定してください。
コードをpushしただけではレジストリは公開されません。

`MENV_SETUP_REGISTRY` または `--registry https://example.com/registry/` で別のHTTPSレジストリを使えます。
更新時は対象を導入したレジストリを再利用します。`--registry` は明示的な変更になります。
Remote の作業場所は既定で `$XDG_DATA_HOME/menv/setup/work/<name>`（未設定時 `~/.local/share/menv/setup/work/<name>`）。
`--workdir /absolute/path` で変更できます。キャッシュ内では実行しません。

取得時は index と定義の version・SHA-256 を照合します。version はソフト本体でなく定義の改訂番号です。
通信失敗時は検証可能な取得済み定義を使い、その旨を表示します。
不正なメタデータ、ハッシュ不一致、版の不一致はエラーです。
新しいindexが示す定義が未取得なら、以前の別の定義に黙って戻りません。
`--offline` でネットワークへのアクセスをせず、キャッシュだけを利用できます。
ハッシュは整合性検証用で、配布元の信頼性を保証する署名ではありません。

## 保存場所

| 内容 | 既定の保存先 |
| --- | --- |
| レジストリ別キャッシュ | `~/.cache/menv/setup/registries/` |
| 成功したinitと前回のオプション | `~/.local/state/menv/setup/installed.json` |
| 各コマンドの終了コード・引数・作業場所 | `~/.local/state/menv/setup/history.jsonl` |
| Remote作業場所 | `~/.local/share/menv/setup/work/` |
| bootstrap専用Python・uv | `~/.local/share/menv/runtime/` |

対応する `XDG_CACHE_HOME` / `XDG_STATE_HOME` / `XDG_DATA_HOME` を指定できます。
ログには引数も残るため、秘密情報をオプションで渡さないでください。
履歴ファイルは一時ファイルから置き換えます。実行はロックして並行更新を防ぎます。

## 問題の切り分け

| 症状 | 確認すること |
| --- | --- |
| me で環境が変わらない | `type me` が関数になっているか |
| knew が見つからない | `me kyopro` と `command -v knew` |
| .venv/bin/python がない | `setup init kyopro` |
| compatible Python missing | `bash "$MENV_ROOT/bootstrap.sh"` |
| gpp がない | 手動配置と ~/.bin の PATH、またはコンパイル設定 |
| Remoteが取得できない | Pagesの公開状況、URL、`--offline` 用キャッシュの有無 |
| Permission denied | `mchmod --dry-run` で確認後 `mchmod` |

定義の記法は [設定仕様](configuration.md) を参照してください。
