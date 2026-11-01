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
kbuild a.cpp --copy
kbuild solution.py -o submission.py --copy
```

kbuild は実行ファイルではなく提出用ソースを作ります。
コンテスト内の既定出力は .build/<問題>/sol.cpp、コンテスト外ではソースの隣の sol.cpp です。
Python の提出用ファイル名は sol.py です。
`--copy` を付けた場合だけ、生成成功後に提出用ソースをクリップボードへコピーします。
コピーに失敗した場合は終了コード 1 を返しますが、生成済みファイルは残ります。

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
自動提出不可・提出失敗時には、後述の共通設定に従って生成済みソースのコピーを試みます。
コピーできても自動提出不可・提出失敗の終了コードは 1 のままです。

## クリップボード

任意のコマンド出力をコピーするには、競プロ環境への切り替えなしで `cat main.cpp | clip` を使えます。[共通 clip コマンド](commands.md#clip)を参照してください。

`kbuild --copy` と `ksub` は `envs/kyopro/.config` の同じ設定を使います。
既存設定に `[clipboard]` がない場合も `auto` として動作します。

```toml
[clipboard]
method = "auto"
command = []
```

`method` は次の 3 種類です。

| 値 | 動作 |
| --- | --- |
| `auto` | SSH_CONNECTION / SSH_TTY があれば OSC 52。ローカルでは設定した `command`、`clip.exe`、`clip`、`wl-copy`、`xclip -selection clipboard`、`xsel --clipboard --input` の順で試し、最後に OSC 52 を試す |
| `command` | `command` のみを実行する。空の配列は設定エラー |
| `osc52` | 外部コマンドを使わず OSC 52 を送る |

`auto` のローカル実行では PATH 上にあるコマンドを試します。menv 自身の `clip` は除外します。起動エラー・非ゼロ終了・5 秒のタイムアウトは失敗として次へ進みます。
`command` には実行ファイルと引数を配列で指定します。生成済みソースの内容を標準入力へ渡し、シェル経由の実行や `{source}` などの置換はしません。`clip.exe` には UTF-8 を BOM 付き UTF-16LE に変換して渡します。

Wayland でコマンドを固定する例です。

```toml
[clipboard]
method = "command"
command = ["wl-copy", "--type", "text/plain;charset=utf-8"]
```

WSL では `command = ["clip.exe"]`、X11 では `command = ["xclip", "-selection", "clipboard"]` または `command = ["xsel", "--clipboard", "--input"]` を指定できます。

SSH 先から接続元の端末のクリップボードへ送る場合は、OSC 52 を明示できます。
`auto` も SSH 接続を検出した場合は OSC 52 を選びます。

```toml
[clipboard]
method = "osc52"
```

OSC 52 は UTF-8 ソースを Base64 化し、制御端末 `/dev/tty` へ送ります。リダイレクトした標準出力へ制御シーケンスは混入しません。
制御端末のない CI などでは失敗します。接続元の端末が OSC 52 に対応し、クリップボード書き込みを許可している必要があります。
tmux 内ではパススルー形式で送るため、tmux 側でもパススルーの許可が必要です。screen や多重の tmux などでは中継できないことがあります。
端末や中継ソフトのペイロード長制限によって、大きな提出用ソースは無視・切り詰められる場合があります。
OSC 52 には成功応答がなく、コマンドの成功表示はシーケンスの送信完了を示すだけです。実際に貼り付けて内容を確認してください。

## 設定

envs/kyopro/.config を編集します。

| 項目 | 用途・同梱値 |
| --- | --- |
| [defaults].site | サイト。atcoder |
| [defaults].language | 言語設定。cpp。knew はソースを生成しない |
| [knew].download_samples | サンプル取得。true |
| [testing].timeout | 各ケースの秒数。2.0 |
| [ksub].test_before_submit | 提出前テスト。false |
| [clipboard].method | コピー方式。auto |
| [clipboard].command | コピー用コマンド配列。空配列 |
| [cpp].build_command / run_command | C++ コンパイル・実行コマンド |
| [cpp].include_dirs | include 検索パス |
| [python].run_command | Python 実行コマンド |

コマンド配列の {source} / {output} はパスに置換されます。
各コマンドの --help で現在の引数を確認できます。
