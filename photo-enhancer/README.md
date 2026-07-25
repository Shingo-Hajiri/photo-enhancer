# photo-enhancer

Google Driveの「加工依頼」フォルダに入れた写真を自動で明るさ・彩度・露出補正し、「加工済み」フォルダに出力するツール。

## セットアップ

### 1. Python環境

```bash
cd photo-enhancer
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Google Drive APIのOAuth認証情報を作成

1. [Google Cloud Console](https://console.cloud.google.com/)で新しいプロジェクトを作成
2. 「APIとサービス」→「ライブラリ」で **Google Drive API** を有効化
3. 「認証情報」→「認証情報を作成」→「OAuthクライアントID」→アプリケーションの種類は **デスクトップアプリ**
4. 作成したクライアントIDの認証情報をJSONでダウンロードし、`photo-enhancer/credentials/credentials.json` として保存

### 3. 初回実行(トークン発行)

```bash
source venv/bin/activate
python3 main.py
```

初回はブラウザが開くのでGoogleアカウントでログインし、アクセスを許可してください。`credentials/token.json` が自動生成されます。以降はブラウザ操作なしで動きます。

Google Driveに「Instagram画像加工」フォルダ(配下に「加工依頼」「加工済み」)が自動で作成されます。

## 使い方

- 「加工依頼」フォルダにスマホ/Driveアプリから写真をアップロードする
- 通常は1日2回(22:00・23:30)自動実行される
- 急ぎのときは手動実行:

```bash
cd photo-enhancer
source venv/bin/activate
python3 main.py
```

## 自動実行(launchd)の登録

```bash
cp com.sweets.photoenhancer.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.sweets.photoenhancer.plist
```

停止する場合:

```bash
launchctl unload ~/Library/LaunchAgents/com.sweets.photoenhancer.plist
```

## ログ・エラー通知

- 実行ログ: `logs/photo_enhancer.log`
- 加工エラーが発生した場合、`.company/secretary/todos/YYYY-MM-DD.md` に通知が追記される
- 加工に失敗した画像は「加工依頼」フォルダに残るので、そのまま次回再試行される

## 設定の変更

`config.py` の `Config` クラスで彩度ブースト量・ガンマ値・安全ネット削除日数などを調整できる。
