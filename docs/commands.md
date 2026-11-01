# 環境切替と共通コマンド

## me

envs/ 内の環境を仮想パスとして扱います。pwd / cd の作業ディレクトリとは別です。

| 操作 | 動作 |
| --- | --- |
| `me` / `me pwd` | 現在の環境パスを表示。非アクティブ時も / と表示 |
| `me ls` | 現在の環境の子ディレクトリを一覧表示 |
| `me menv` | 同名の子・兄弟環境を探し、なければ共通環境へ |
| `me menv/kyopro` | envs/kyopro へ |
| `me '~'` / `me '~/kyopro'` | 共通環境 / ルートから指定した環境へ。引用して Bash の ~ 展開を防ぐ |
| `me name` | 現在の環境の子、次に兄弟から探す |
| `me ./name` / `me ../name` | 環境パスに対する相対指定 |
| `me ..` | 親環境へ。共通環境からは終了 |
| `me .` | 現在の環境を再適用 |
| `me -` | 直前の環境へ戻る |
| `me /` | 終了し、保存していた PATH / PS1 を復元 |
| `me --help` | ヘルプ |

共通環境と各祖先環境の .bin、.venv/bin、.tools が PATH に追加され、深い環境が先に検索されます。
.tools/<tool>/bin があればそこを、なければ .tools/<tool> を追加します。
プロンプトには環境名が付き、祖先名の省略形は各環境の .name で指定できます。

## clip

標準入力の UTF-8 テキストをコピーする共通コマンドです。通常の menv 導入時の PATH 設定だけで使用でき、`me kyopro` や venv の準備は不要です。
`.bin/clip` は実行ファイルなので、alias を追加する必要はありません。Neovim などの外部プロセスからも呼び出せます。

```bash
cat main.cpp | clip
clip < main.cpp
printf '日本語 😀\n' | clip
```

Neovim では `:w !clip` で現在のバッファをコピーできます。yank のクリップボード連携は Neovim 側の別設定です。

既定の `auto` は次のように選びます。

| 環境 | 動作 |
| --- | --- |
| SSH_CONNECTION または SSH_TTY がある | OSC 52 で接続元の端末へ送信。リモート側のコピーコマンドは使わない |
| ローカル | clip.exe、clip、wl-copy、xclip、xsel の順に試し、最後に OSC 52 |

menv 自身の `clip` はコピー先候補から除外し、再帰呼び出しを防ぎます。
WSL の `clip.exe` には UTF-8 から BOM 付き UTF-16LE に変換して渡します。`iconv` や CP932 用の alias は不要です。
その他の外部コマンドには入力のバイト列をそのまま渡します。

方式を明示する場合は次のように指定できます。`--command` 以降はすべてコピー先コマンドの引数です。

```bash
cat main.cpp | clip --method osc52
cat main.cpp | clip --method command --command wl-copy --type text/plain
```

`clip` 自体は競プロの `.config` を読みません。`kbuild --copy` / `ksub` は競プロの設定を引き続き使い、同じ共通処理を呼び出します。

### 既存の alias からの移行

すでに `alias clip='iconv -t cp932 | clip.exe'` を書いている場合は、`.bashrc` のその行を削除し、現在のシェルでも次を実行します。

```bash
unalias clip
command -v clip
```

`command -v clip` が `$MENV_ROOT/.bin/clip` を指していれば移行完了です。新しい VPS では通常の menv 導入以外の alias 設定は不要です。

### OSC 52 の条件

接続元の端末が OSC 52 に対応し、クリップボード書き込みを許可している必要があります。VPS 側への外部コピーコマンドの導入は不要です。
制御シーケンスは `/dev/tty` へ送るため、入力のパイプや標準出力のリダイレクトと併用できます。制御端末がない場合は失敗します。
tmux 内ではパススルーの許可が必要で、screen や多重 tmux などでは中継できないことがあります。
端末・中継ソフトの長さ制限によって大きなテキストが無視・切り詰められる場合があります。
OSC 52 は成功応答を返さないため、終了コード 0 は送信完了を示すだけです。実際の貼り付け内容を確認してください。コピー処理に失敗した場合の終了コードは 1 です。

## mcheck

.toml に基づき、システムパッケージ、ツール、venv、pip パッケージ、コマンドを確認します。

```bash
mcheck kyopro
mcheck kyopro --install
mcheck kyopro --update
mcheck kyopro --sync --strict
```

| 引数 | 動作 |
| --- | --- |
| 環境名なし / . | 現在の環境。環境外では共通環境 |
| menv / '~' | 共通環境 |
| kyopro / menv/kyopro / '~/kyopro' | 指定した環境 |
| .. | 現在の環境の親 |
| --install | 環境内の不足依存だけを導入 |
| --update | [update] の環境内依存だけを更新 |
| --sync | 導入と更新を両方実行 |
| --strict | 検査結果に NG があれば終了コード 1 |

[check] は検査だけです。--install / --sync でもシステムパッケージやグローバルコマンドは導入しません。
通常の検査でも [update].pip と [[update.github]] の更新確認を実行します。
--strict がなければ検査結果が NG でも通常は終了コード 0 です。引数や設定のエラーは別途失敗します。
名前の解決は me と異なり、通常の環境名は envs/ 直下から指定します。

## mchmod

```bash
mchmod --dry-run
mchmod
```

MENV_ROOT 以下の .bin にある shebang 付きファイルに実行権限を追加します。
venv、.venv、__pycache__ は除外します。--dry-run は変更予定のみ表示します。
home/.bin の保管用ファイルも対象です。

## mserver

```bash
mserver --root ./music --host 127.0.0.1 --port 8000
```

既定は現在のディレクトリ、127.0.0.1:8000 です。Ctrl+C で停止します。
共通 HTTP 機能に加え、envs/*/.lib/server/routes.py の register(router) を読み込みます。
音楽管理 UI は /song/ です。[音楽管理](song.md)を参照してください。
