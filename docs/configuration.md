# 設定とプラグイン構成

## 依存定義 .toml

共通環境はルートの .toml、各環境は envs/<name>/.toml を使用します。
mcheck は指定した環境のファイルを読み、祖先の依存定義は自動合成しません。

```toml
[system]
packages = ["g++"]

[tools]
names = []

[commands]
names = ["g++", "oj"]

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
| [system].packages | dpkg で検査し、--install で apt により導入 |
| [tools].names | 環境固有の tools.py で検査・導入 |
| [commands].names | 環境内とグローバル PATH から探すコマンド |
| [venv].path | 環境からの仮想環境パス。既定 .venv |
| [venv].python | venv 作成コマンド。既定 python3 |
| [venv].packages | 必要な pip パッケージ。name @ URL も対応 |
| [update].pip | 更新確認・更新する pip パッケージ名 |
| [update].tools | 更新フックを呼ぶツール名 |

現在の me と競プロラッパーは .venv/bin を使用するため、通常は [venv].path を変更しません。
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
