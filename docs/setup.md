# 導入・更新

## 必要な環境

Ubuntu / Debian 系 Linux または WSL と Bash、Git、Python 3.11 以上（tomllib を使用）、python3-venv が必要です。
apt による導入には sudo を使用します。

clone と Bash 設定は [README](../README.md#導入) を参照してください。
別の場所に clone する場合は MENV_ROOT をその絶対パスに変更します。
me はシェルの状態を変えるため、関数から source して使います。

```bash
source "$HOME/.bashrc"
mchmod
mcheck menv --install
mcheck kyopro --install
me kyopro
```

mcheck のラッパーは Python / venv がない場合に導入するか質問します。
それ以外の不足依存を導入するには --install を指定します。
設定した pip 更新対象の確認にもネットワーク接続を使います。

## C++ の準備

同梱の `envs/kyopro/.config` はコンパイルに gpp を使用します。自動配置されないため、使用する場合はコピーします。

```bash
mkdir -p "$HOME/.bin"
cp "$MENV_ROOT/home/.bin/gpp" "$HOME/.bin/gpp"
chmod +x "$HOME/.bin/gpp"
```

`~/.bashrc` に `export PATH="$HOME/.bin:$PATH"` を追加し、新しい Bash を開きます。
gpp は GCC の C++23 モード、最適化、ライブラリ検索パスを設定します。
-d で DEBUG と AddressSanitizer / UndefinedBehaviorSanitizer を有効にします。
コンパイラの指定は CXX、PCH の詳細は [GPP-PCH.md](../home/.bin/GPP-PCH.md) を参照してください。

使用する自作ライブラリは `~/library/mone-library`、ACL は `~/library/ac-library` に別途配置します。
これらはリポジトリに含まれていません。
提出用ソースの include 展開にも必要な検索パスは [競プロ設定](kyopro.md#提出用ソースの生成) に追加します。

gpp を使わない場合は `envs/kyopro/.config` の [cpp] を変更します。

```toml
[cpp]
build_command = ["g++", "-std=gnu++23", "-O2", "{source}", "-o", "{output}"]
run_command = ["{output}"]
include_dirs = []
```

## 更新

```bash
git -C "$MENV_ROOT" pull --ff-only
mchmod
mcheck kyopro --sync
```

git pull はソースを更新し、--sync は対象環境の不足依存を導入して設定した依存を更新します。
ローカルで設定を編集した場合は pull 前に差分を確認してください。
手動コピーした gpp も、更新したい場合は再コピーします。

## 問題の切り分け

| 症状 | 確認すること |
| --- | --- |
| me で環境が変わらない | `type me` で関数になっているか確認 |
| knew などが見つからない | `me kyopro` と `command -v knew` |
| .venv/bin/python がない | `mcheck kyopro --install` |
| Permission denied | `mchmod --dry-run` で確認後、`mchmod` |
| gpp がない | 手動配置と ~/.bin の PATH、またはコンパイル設定 |
| sol.cpp で include が見つからない | .config の include_dirs または kbuild -I |

現在の依存定義では mcheck は gpp や自作ライブラリの配置を検査しません。
実装が存在しない旧ラッパー kahc、kconf、kdel、klogin、kprob、kstre は削除しました。
設定は .config を編集し、ログインは必要に応じて oj login を使います。
