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
   - Scopes: `bot`
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

## ファイル構成

```
ogp_bot/
├── bot.py              # エントリポイント
├── config.py           # 環境変数読み込み
├── fetchers/
│   ├── base.py         # Fetcher基底クラス・レジストリ
│   └── makerworld.py   # MakerWorld用fetcher
├── .env.example        # 環境変数テンプレート
└── requirements.txt
```

## 対応サイトの追加

`fetchers/` に新ファイルを追加し、`Fetcher` を継承して `REGISTRY.append()` するだけ。

```python
from .base import Fetcher, OGPData, REGISTRY

class MySiteFetcher(Fetcher):
    def match(self, url):
        # 対応URLなら識別子を返す、それ以外はNone
        ...

    async def fetch(self, identifier, url, session):
        # OGPData を返す
        ...

REGISTRY.append(MySiteFetcher())
```
