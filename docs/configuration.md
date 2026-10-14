# 設定とプラグイン構成

## 依存定義 .toml

共通環境はルートの .toml、各環境は envs/<name>/.toml を使用します。
mcheck は指定した環境のファイルを読み、祖先の依存定義は自動合成しません。

```toml
[check]
commands = ["g++", "oj"]
packages = ["g++"]

[install]
tools = []

[venv]
path = ".venv"
python = "python3"
packages = ["online-judge-tools"]

[update]
pip = ["online-judge-tools"]
tools = []
```

| 項目 | 用途 |
| --- | --- |
| [check].commands | PATH と環境内でのコマンドの存在確認のみ |
| [check].packages | dpkg によるシステムパッケージの確認のみ |
| [install].tools | 環境の .tools 内に導入するツール |
| [venv].path | 環境内の仮想環境パス。既定 .venv |
| [venv].python | venv 作成に使う既存 Python。既定 python3 |
| [venv].packages | ローカル venv に導入する pip パッケージ。name @ URL も対応 |
| [update].pip | PyPI から更新確認・更新する pip パッケージ名 |
| [update].tools | 環境の tools.py の更新フックを呼ぶツール名 |

--install / --sync でも apt、sudo、グローバル pip は実行しません。
Python 自体・venv モジュール・コンパイラなどはユーザーが管理します。
旧 [system].packages と [commands].names は検査専用として互換対応し、[tools].names は [install].tools の旧形式として受け付けます。

venv の絶対パス・環境外へのパス・外への symlink は拒否します。
既存 venv は Python の sys.prefix を確認し、システムパッケージを継承する venv は拒否します。
pip の書き込み先を変える環境変数・設定ファイルも無効にします。
.tools とその中の外向き symlink も拒否します。
ツールのフックは信頼するリポジトリ内の Python コードで、OS のサンドボックスではありません。
フックは .tools 内だけを書き換える契約とします。
現在の me と競プロラッパーは .venv/bin を使用するため、通常は [venv].path を変更しません。

## GitHub リリースによる更新判定

```toml
[venv]
path = ".venv"
packages = ["yt-dlp"]

[update]
pip = []
tools = []

[[update.github]]
package = "yt-dlp"
repository = "https://github.com/yt-dlp/yt-dlp"
tag_prefix = "v" # 省略時も v。タグに付いていなければそのまま
```

GitHub の最新安定版リリースの tag_name と、venv に導入済みのパッケージバージョンを比較します。
通常実行では確認だけ、新しい版がある場合に --update / --sync でその版を PyPI から導入します。
最新版と同じ、またはローカルの方が新しい場合は何もしません。
GitHub の main ブランチから直接インストールする方式ではありません。
タグが pip バージョンに対応するプロジェクトが対象で、package は [venv].packages にも宣言します。
GitHub と PyPI の公開タイミングがずれ、指定版が PyPI にまだない場合は失敗として表示します。
GitHub API の通信失敗・レート制限・比較できないタグも失敗として扱い、推測で更新しません。
--strict なら確認失敗や更新待ちも終了コード 1 になります。
この方式は pip パッケージ向けです。.tools の更新は既存のツールフックを使います。
ツールは通常の検査では導入済みか確認するだけで、最新版かは判定しません。

## 環境を追加する

envs/<name>/ に必要な構成を作ります。

| パス | 役割 |
| --- | --- |
| .bin/<command> | コマンドの入口 |
| .lib/ | 実装 |
| .toml | 依存定義 |
| .venv/ | Python 仮想環境（生成物） |
| .tools/ | 環境専用ツール（生成物） |
| .name | 祖先環境のプロンプト用省略名（任意） |

ツール管理を追加する場合は .lib/tools.py に次の関数を用意します。

```python
def has_tool(name: str) -> bool: ...
def install_tool(name: str) -> bool: ...
def update_tool(name: str) -> bool: ...
```

実装例は [song の tools.py](../envs/song/.lib/tools.py) です。
サーバー拡張は .lib/server/routes.py の register(router) で登録します。
.bin のラッパーを追加する際は実装ファイルが存在することを確認し、実装を削除したらラッパーとドキュメントも削除します。

## コマンド固有の設定

競プロの動作設定は envs/kyopro/.config（TOML）です。
依存を導入する .toml とは役割が異なります。[競プロ設定](kyopro.md#設定)を参照してください。
音楽ワークスペースの .config/ は、作業データ側のディレクトリです。
