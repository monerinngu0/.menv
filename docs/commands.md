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
