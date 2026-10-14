# 競技プログラミング

[導入手順](setup.md)に従い venv とコンパイラを準備してから `me kyopro` を実行します。
対応ソースは .cpp と .py です。

## コンテスト取得

```bash
knew abc400
knew 2267 --site codeforces
knew abc400 --directory ~/contests --no-download
```

knew はコンテスト情報と、既定ではサンプルを取得します。
保存先は現在のディレクトリ配下のコンテスト ID で、既存の保存先は上書きしません。
.contest にメタデータ、各問題名のディレクトリにテストを保存します。
ソースファイルのテンプレートは生成しないため、コンテスト直下に a.cpp / a.py などを作成します。

## ローカルテスト

```bash
cd abc400
ktest a
ktest a --timeout 3 -I ~/library/ac-library
```

.contest を祖先から探してコンテストとして扱います。
テストは問題ディレクトリの in1 / out1、in2 / out2 の組です。
実行ファイルは .build/<問題>/run に生成します。
判定結果は AC / WA / RE / TLE です。

コンテスト外ではソースファイルを指定します。省略時は main.cpp です。
テストデータはソースと同じディレクトリに置きます。

```bash
ktest main.cpp
ktest solution.py
```

追加ケースは in3 / out3 などを手動で配置します。
現在の実装に --add-case、--list-cases、knew --manual はありません。

## 提出用ソースの生成

```bash
kbuild a.cpp -I ~/library/mone-library -I ~/library/ac-library
kbuild main.cpp -o submission.cpp
```

kbuild は実行ファイルではなく提出用ソースを作ります。
コンテスト内の既定出力は .build/<問題>/sol.cpp、コンテスト外ではソースの隣の sol.cpp です。
Python の提出用ファイル名は sol.py です。

C++ ではソースのディレクトリ、次に include_dirs でヘッダーを探し、見つかった include を再帰的に展開します。
見つからない include は残ります。同じファイルは一度だけ展開します。
gpp に組み込まれた -I はこの展開処理には引き継がれません。

.config に検索パスを指定すると毎回 -I を渡す必要がありません。

```toml
[cpp]
build_command = ["gpp", "{source}", "-o", "{output}"]
run_command = ["{output}"]
include_dirs = ["~/library/mone-library", "~/library/ac-library"]
```

### 現在の展開処理の制約

この処理は C++ プリプロセッサではなく行単位の置換です。
ヘッダーは一度だけ読み込める構成にし、include は単独行で記述します。
マクロで指定する include、末尾コメント付き include、条件分岐の評価には対応しません。
条件付き include も条件を評価せず展開し、重複ファイルは省略するため、異なる条件から同じヘッダーを読む構成は避けてください。
自作ライブラリ用のディレクトリだけを検索パスに指定し、生成したソースを確認・コンパイルしてください。

## 提出

```bash
oj login https://atcoder.jp/
ksub a --test
```

ksub はコンテスト内で使い、提出用ソースを生成してからサイトの提出処理を呼びます。
--test は提出前にローカルテストを行い、--no-test は無効にします。
同梱設定では提出前テストは既定で無効です。
AtCoder の提出言語は .lib/submission.py に定義されています。
Codeforces は自動提出に対応していません。提出できない場合は生成済みソースを手動提出します。
clip.exe または clip があればクリップボードへのコピーも試みます。自動提出不可は終了コード 1 です。

## 設定

envs/kyopro/.config を編集します。

| 項目 | 用途・同梱値 |
| --- | --- |
| [defaults].site | サイト。atcoder |
| [defaults].language | 言語設定。cpp。knew はソースを生成しない |
| [knew].download_samples | サンプル取得。true |
| [testing].timeout | 各ケースの秒数。2.0 |
| [ksub].test_before_submit | 提出前テスト。false |
| [cpp].build_command / run_command | C++ コンパイル・実行コマンド |
| [cpp].include_dirs | include 検索パス |
| [python].run_command | Python 実行コマンド |

コマンド配列の {source} / {output} はパスに置換されます。
各コマンドの --help で現在の引数を確認できます。
