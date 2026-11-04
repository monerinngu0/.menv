# 設定とプラグイン構成

## セットアップ定義 .toml

Local は `envs/<name>/.toml` を探索します。共通環境はルートの `.toml`（`local:menv`）です。
子envの定義は独立し、祖先の定義を自動実行しません。
旧mcheck形式は受け付けず、未知のキーも入力ミスとして拒否します。

```toml
name = "example"
version = 1
description = "Example setup"

[options.branch]
description = "Clone branch"
default = "main"
choices = ["main", "develop"]

[init]
description = "{branch}をrepoへcloneします。既にrepo/.gitがあればスキップします。"

[[init.steps]]
run = ["git", "clone", "--branch", "{branch}", "https://github.com/example/repo.git", "repo"]
unless_path = "repo/.git"

[update]
description = "repoをfast-forwardで更新します。"
commands = [
    ["git", "-C", "repo", "pull", "--ff-only"],
]
```

`name` はLocalのenv名またはRemoteのindexのキーと一致させます。ネストしたenvは `parent/child`。
`version` は1以上の整数で、定義を変更したら増やします。ソフトウェア本体のバージョンとは独立です。
共通・各アクションの `description` は必須です。影響、既存ファイルの上書き、更新方針を記述します。
`init` は必須、`update` は任意。update未定義の対象の更新はエラーになります。

各アクションは `commands` と `steps` の片方だけを指定します。空配列は拒否します。
`commands` は非空の引数配列の列、`steps` は `run` と任意の `cwd` / `unless_path` を持つテーブルの列です。
各プロセスは独立しています。`cd`、シェル変数、export は次のプロセスへ引き継がれません。
実行は `shell=False`。パイプや条件分岐が必要なら `['bash', '-euc', '...']` を明示的に定義します。

## オプションと展開

オプション値はすべて文字列です。`description` は必須、`default` と文字列配列 `choices` は任意です。
デフォルトなしの値は必須入力になります。`choices` があれば入力をその一覧に限定します。
対話端末では各値を入力し、空入力は前回値またはデフォルトを採用します。
`--set key=value` は繰り返し指定できます。未知のキー、重複指定はエラーです。
`-y` または非対話入力では質問せず、明示値 → 前回値 → デフォルトの順に採用します。
必要な値がなければ実行せずに失敗します。

コマンド各引数・説明・cwd・unless_path の `{name}` を1回だけ置換します。
オプション値自体は展開しません。`$HOME` や `~` を入力値として渡しても、引数内では自動展開しません。
入力した空白、クォート、`;`、`$()` は1つの引数の内容です。
シェルを使う定義では入力値をコードに直接埋めず、位置引数として渡してください。
リテラルの波括弧は `{{` / `}}`。シェルの `${name}` は置換しません。

| 組み込み変数 | 内容 |
| --- | --- |
| `{root}` | MENV_ROOTの絶対パス |
| `{env}` / `{work}` | 当該定義の作業場所 |
| `{home}` | ユーザーのホーム |
| `{python}` | setup実行中のPython |
| `{data}` | XDG_DATA_HOME/menv/setup |
| `{cache}` | XDG_CACHE_HOME/menv/setup |
| `{state}` | XDG_STATE_HOME/menv/setup |

これらの名前をオプション名には使えません。未知の `{name}` は計画作成時のエラーです。

Localの作業場所は各envのルート。Remoteは専用作業場所または `--workdir` で指定した場所です。
stepの相対 `cwd` はこの作業場所が基準（既定 `.`）。相対 `unless_path` はそのstepのcwdが基準です。
作業場所は承認後に作成します。stepで別のcwdを使う場合は、先行stepで用意してください。
`unless_path` はそのstepの実行直前に評価するため、先行stepで作ったファイルも確認できます。

確認した計画をそのまま実行し、途中でTOMLの再取得・再解析はしません。
呼び出し先スクリプトやネットワーク配布物の内容は別途変化し得ます。信頼する定義を使用してください。
冪等性、インストール先、ソフトの版管理は定義作成者の責任で、任意コマンドをOSから隔離する仕組みではありません。

## Remote定義を追加する

`registry/packages/<name>.toml` を作り、次を実行します。

```bash
python3 scripts/build_registry.py
python3 scripts/build_registry.py --check
```

`registry/index.json` に path・version・SHA-256・説明が生成されます。
両方をcommitし、Pages公開workflowを実行します。レジストリのbase URLはHTTPSが必須です。
取得した定義はレジストリURL別・内容ハッシュ別にキャッシュします。
公開方法と通信失敗時の扱いは [導入手順](setup.md#remote-レジストリ) を参照してください。

## 環境を追加する

| パス | 役割 |
| --- | --- |
| `.bin/<command>` | コマンドの入口 |
| `.lib/` | 各env固有の実装、導入用スクリプト |
| `.toml` | init/update定義 |
| `.venv/` | Python仮想環境（生成物） |
| `.tools/` | 環境専用ツール（生成物） |
| `.name` | 祖先環境のプロンプト用省略名（任意） |

setup本体へenv固有のフックを登録する必要はありません。
同梱定義は `.lib/venv_tools.py` を明示的に呼んで隔離venvを作成し、pipの書き込み先設定を無効にして導入します。
songは自身の `.lib/tools.py` を呼び、ffmpegとdenoを導入します。
サーバー拡張は `.lib/server/routes.py` の `register(router)` で登録します。

競プロの動作設定は `envs/kyopro/.config`（TOML）、音楽ワークスペースの `.config/` は作業データ側のディレクトリです。
セットアップ定義とは役割が異なります。[競プロ設定](kyopro.md#設定)も参照してください。
