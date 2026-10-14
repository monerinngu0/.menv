# menv

Bash で用途ごとの開発環境を切り替える個人用ツールです。共通機能をルートに置き、競プロ・音楽管理を `envs/` に分けています。
`me` は現在のシェルの PATH とプロンプトを変更します。作業ディレクトリは変更しません。

## 導入

Ubuntu / Debian 系 Linux または WSL、Bash、Git、Python 3.11 以上と venv を想定しています。

```bash
git clone https://github.com/monerinngu0/.menv.git "$HOME/.menv"
```

`~/.bashrc` に次を追加します。

```bash
export MENV_ROOT="$HOME/.menv"
export PATH="$MENV_ROOT/.bin:$PATH"
me() { source "$MENV_ROOT/.bin/me" "$@"; }
```

新しい Bash を開き、必要な環境を準備します。

```bash
mchmod --dry-run
mchmod
mcheck kyopro --install
me kyopro
```

初期設定では別途 `gpp` の配置が必要です。[導入手順](docs/setup.md)を参照してください。

## 基本操作

```bash
me ls           # 子環境を一覧表示
me kyopro       # 競プロ環境へ切替
me menv/song    # 音楽管理環境へ切替
me pwd          # 現在の環境を表示
me /            # 保存していた PATH / PS1 を復元
```

## ドキュメント

- [導入・更新・トラブルシューティング](docs/setup.md)
- [環境切替と共通コマンド](docs/commands.md)
- [設定ファイルとプラグイン構成](docs/configuration.md)
- [競技プログラミング](docs/kyopro.md)
- [音楽管理](docs/song.md)

## 構成

| パス | 内容 |
| --- | --- |
| `.bin/` | 共通コマンドの入口 |
| `.lib/` | 共通実装、HTTP サーバー |
| `.toml` | 共通環境の依存定義 |
| `envs/kyopro/` | コンテスト取得、テスト、提出用ソース生成、提出 |
| `envs/song/` | 音楽ワークスペース、一覧、差分、パッケージ化 |
| `home/` | ホームへ手動配置するファイルの保管場所 |
| `docs/` | 利用・設定ドキュメント |

`home/` は実行時のホームではありません。必要なファイルを実際の `~/` に配置します。
