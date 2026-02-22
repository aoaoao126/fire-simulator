# 📘 FIRE シミュレーター – デプロイ手順

iPadやスマホから **PCを開かずに** 利用するためのデプロイ手順です。  
**Streamlit Community Cloud**（無料）を使用します。

---

## 前提条件

- [GitHub](https://github.com/) アカウント
- [Streamlit Community Cloud](https://share.streamlit.io/) アカウント（GitHubでログイン）

---

## 手順

### 1. GitHubリポジトリを作成

1. [GitHub](https://github.com/) にログイン
2. 右上の **「+」 → 「New repository」** をクリック
3. 以下を入力：
   - **Repository name**: `fire-simulator`
   - **Visibility**: `Private`（個人データを含まないため Public でもOK）
4. **「Create repository」** をクリック

### 2. ローカルのコードをプッシュ

PowerShellまたはターミナルで以下を実行：

```powershell
cd C:\Users\Suzuki\.gemini\antigravity\scratch\fire-simulator

git init
git add .
git commit -m "Initial commit: FIRE simulator"
git branch -M main
git remote add origin https://github.com/<あなたのユーザー名>/fire-simulator.git
git push -u origin main
```

> ⚠️ `<あなたのユーザー名>` を自分のGitHubユーザー名に置き換えてください。

### 3. Streamlit Community Cloudにデプロイ

1. [share.streamlit.io](https://share.streamlit.io/) にアクセス
2. **「New app」** をクリック
3. 以下を設定：
   - **Repository**: `<あなたのユーザー名>/fire-simulator`
   - **Branch**: `main`
   - **Main file path**: `app.py`
4. **「Deploy!」** をクリック
5. 数分でデプロイが完了し、URLが発行されます（例: `https://fire-simulator-xxxxx.streamlit.app`）

### 4. iPadからアクセス

1. iPadの **Safari** を開く
2. 発行されたURL（`https://xxxx.streamlit.app`）にアクセス
3. 🎉 完了！

#### ホーム画面に追加（おすすめ）

Safariで開いた状態で：
1. **共有ボタン（□↑）** をタップ
2. **「ホーム画面に追加」** を選択
3. アプリのようにワンタップで起動できるようになります

---

## データの管理について

Streamlit Cloud上ではサーバー再起動時にローカルデータが消えます。  
以下の方法でデータを管理してください：

### 設定の保存
1. サイドバーの **「📥 JSONエクスポート」** ボタンでデータをダウンロード
2. iPadの「ファイル」アプリに保存されます

### 設定の復元
1. サイドバーの **「📤 JSONインポート」** でダウンロードしたJSONファイルを選択
2. 設定が復元されます

> 💡 シミュレーション条件を変更したら、必ず **JSONエクスポート** しておきましょう。

---

## コードの更新

コードを修正した場合、GitHubにプッシュすると自動的にStreamlit Cloudに反映されます：

```powershell
cd C:\Users\Suzuki\.gemini\antigravity\scratch\fire-simulator
git add .
git commit -m "Update: 変更内容の説明"
git push
```

---

## トラブルシューティング

| 問題 | 対処法 |
|------|--------|
| デプロイが失敗する | Streamlit Cloudのログを確認。`requirements.txt` に不足がないか確認 |
| グラフが表示されない | iPadのSafariを最新版にアップデート |
| データが消えた | JSONエクスポートから復元。こまめにエクスポートする習慣を |
| 画面が崩れる | iPadを横向きにする。Safari設定で「デスクトップ用Webサイト」をOFFに |
