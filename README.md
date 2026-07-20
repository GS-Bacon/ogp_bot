# OGP Bot

MakerWorldなど、OGPクローラーが弾かれるサイトのURLがDiscordチャンネルに貼られたとき、ボットが代わりにEmbedを投稿するDiscord Bot。

## 仕組み

MakerWorldのページ本体はCloudflareのJSチャレンジで保護されているため、DiscordのOGPクローラーが弾かれる。  
このBotは内部APIから直接JSON取得することで回避し、タイトル・画像・説明・統計をEmbedで表示する。

## セットアップ

### 1. 依存インストール

```bash
pip install -r requirements.txt
```

### 2. Discord Developer Portal の設定

1. [discord.com/developers/applications](https://discord.com/developers/applications) でアプリを作成
2. **Bot** タブ → **Message Content Intent** を **ON** にして保存
3. **OAuth2 → URL Generator** でBotをサーバーに招待
   - Scopes: `bot` / `applications.commands`
   - Bot Permissions: `Send Messages` / `Embed Links`

### 3. 環境変数

```bash
cp .env.example .env
# .env を開いて DISCORD_TOKEN に Botトークンを設定
```

### 4. 起動

```bash
python3 bot.py
```

## サーバーごとの OGP 表示設定

サーバー管理者は `/ogp-block` slash command で、そのサーバーで OGP を出さないサイトを選択できる。

- 実行できるのは **Manage Server** 権限保持者のみ
- ephemeral な Embed が返り、対応サイト一覧が表示される
- multi-select ドロップダウンでチェックしたサイトはそのサーバーで OGP 非表示になる
- 設定は `data/blocklist.json` に guild ID 単位で保存される(bot 再起動後も保持)

## ファイル構成

```
ogp_bot/
├── bot.py              # エントリポイント / slash command 登録
├── config.py           # 環境変数読み込み
├── blocklist.py        # guild ごとのブロックリスト永続化
├── ui.py               # /ogp-block の Embed + Select View
├── fetchers/
│   ├── base.py         # Fetcher基底クラス・レジストリ
│   ├── makerworld.py
│   ├── aliexpress.py
│   └── yahoo_auction.py
├── data/               # blocklist.json などのランタイムデータ(gitignored)
├── .env.example        # 環境変数テンプレート
└── requirements.txt
```

## 対応サイトの追加

`fetchers/` に新ファイルを追加し、`Fetcher` を継承して `REGISTRY.append()` するだけ。`KEY`(保存用の安定 ID)と `DISPLAY_NAME`(`/ogp-block` UI に出す表示名)を必ず定義する。

```python
from .base import Fetcher, OGPData, REGISTRY

class MySiteFetcher(Fetcher):
    KEY = "mysite"          # 安定 ID(blocklist の保存キー)
    DISPLAY_NAME = "MySite" # UI 表示名

    def match(self, url):
        # 対応URLなら識別子を返す、それ以外はNone
        ...

    async def fetch(self, identifier, url, session):
        # OGPData を返す
        ...

REGISTRY.append(MySiteFetcher())
```

fetcher を追加すると `/ogp-block` の選択肢に自動で追加される。
