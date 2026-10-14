# 音楽管理

## 準備とワークスペース

```bash
mcheck song --install
me song
sinit ~/music
cd ~/music
scat favorites
```

song 環境の依存は yt-dlp、ffmpeg / ffprobe、deno です。
yt-dlp は .venv、ffmpeg / deno は .tools 内で管理します。
`mcheck song` で GitHub の yt-dlp 安定版を確認し、`mcheck song --update` で必要な場合だけ更新します。
設定方法は [GitHub 更新設定](configuration.md#github-リリースによる更新判定) を参照してください。
sinit は .config/workspace と .config/config.json を作成します。
カテゴリの音源は <category>/song/、一覧は <category>/.config/song.json に保存します。

## コマンド

| コマンド | 動作 |
| --- | --- |
| sinit [dir] | 指定先（省略時は現在地）をワークスペースにする |
| scat <category> | カテゴリを作成 |
| sadd -c <category> URL | カテゴリへ音源を取得 |
| sadd -d DIR URL | 指定ディレクトリへ音源を取得 |
| slist [category] | カテゴリの song.json を再生成。省略時は全カテゴリ |
| sdel <category> | 音源を番号で選び、確認して削除 |
| sdiff <song.json> | クライアントの一覧との差分を .temp/diff.json に生成 |
| spack [json_path] | 差分またはスナップショットから ZIP を作成 |

sadd は --playlist、既存ファイルの再取得には --force を指定できます。
spack は --all、--category、--select、--output、--all-music-no-json、--keep-temp に対応します。
引数の詳細は sadd / sdiff / spack の --help で確認できます。

## ブラウザ UI

ワークスペースを公開ルートに指定します。

```bash
mserver --root ~/music
```

ブラウザで http://127.0.0.1:8000/song/ を開きます。
mserver は有効な me 環境に関係なく、各環境のサーバールートを読み込みます。
WSL から LAN に公開する設定の参考は [既存のサーバーメモ](../envs/song/.lib/server/README.md) です。
メモ内の IP アドレスとネットワーク範囲は、使用環境に合わせて変更してください。
