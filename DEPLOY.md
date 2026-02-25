# FIRE シミュレーター v3.0（意思決定対応版） – デプロイ手順

iPadやスマホから **PCを開かずに** いつでもシミュレーションを行うためのデプロイ手順です。  
**Streamlit Community Cloud**（無料）を使用することで、自分専用のWebアプリとして公開できます。

---

## デプロイの全体像

1. **GitHub** にコードをアップロード（一度だけ）
2. **Streamlit Cloud** と連携（一度だけ）
3. **iPadのブラウザ** でアクセス ＆ ホーム画面に追加

---

## 1. 準備するもの

- [GitHub](https://github.com/) アカウント
- [Streamlit Community Cloud](https://share.streamlit.io/) アカウント（GitHubでログイン）

---

## 2. GitHubへのプッシュ（PCでの作業）

ターミナル（PowerShell等）で、プロジェクトのディレクトリに移動して以下を実行します。

```powershell
# 1. 初期化
git init

# 2. ファイルをすべて追加
# 次のファイル/ディレクトリが含まれていることを確認してください：
# app.py, pages/, flight_sim_engine.py, flight_chart.py, simulation.py, etc.
git add .

# 3. コミット（記録）
git commit -m "feat: FIRE意思決定シミュレーター「Antigravity」追加"

# 4. メインブランチの設定
git branch -M main

# 5. リモートリポジトリ（GitHub）と紐付け
# ※ <USER> は自分のGitHubユーザー名、<REPO> は作成したリポジトリ名に置き換えてください
git remote add origin https://github.com/<USER>/<REPO>.git

# 6. アップロード
git push -u origin main
```

---

## 3. Streamlit Cloudへのデプロイ

1. [share.streamlit.io](https://share.streamlit.io/) にアクセスし、GitHubでサインインします。
2. **「New app」** をクリックします。
3. **「Use existing repo」** を選択し、以下を入力：
   - **Repository**: `あなたのユーザー名/リポジトリ名`
   - **Main file path**: `app.py`
4. **「Deploy!」** をクリックします。
5. **風船が飛んだら成功です！** 数分であなた専用のURL（例: `https://xxxx.streamlit.app`）が発行されます。

---

## iPad / スマホでの使い方

発行されたURLにアクセスできたら、以下の設定を行うと「PC不要」で快適に使えます。

### ページの切り替え
- 画面左側のサイドバー上部に **「1_モンテカルロ_シミュレーター」** と **「2_🛡️_FIRE体験」** のメニューが表示されます。
- 初期段階では「1_モンテカルロ_シミュレーター」が表示されるので、体験モードを使う際はサイドバーから切り替えてください。

### ホーム画面に追加（Safari推奨）
1. iPadのSafariで発行されたURLを開きます。
2. 画面右上の **共有ボタン（□↑）** をタップします。
3. **「ホーム画面に追加」** を選択します。
4. ホーム画面にアイコンが表示され、次からは**ワンタップでアプリのように起動**できます。

### 画面の最適化
- **iPad**: 横向き（Landscape）で使用すると、グラフとサイドバーが最も綺麗に表示されます。
- **スマホ**: グラフをタップすると拡大表示できます。

---

## データの管理（重要）

Streamlit Cloudは「無料の砂場」のような環境のため、**サーバーが休止すると入力したデータが初期化されます。**  
以下の運用がおすすめです：

1. **JSONエクスポート**: シミュレーション条件が決まったら、サイドバーの下部にある「JSONエクスポート」でiPad内に保存してください。
2. **JSONインポート**: 次回起動時、保存したJSONを読み込めば瞬時に「自分専用の設定」が復元されます。

---

## アップデート方法
今後、私がコードを修正した場合は、PCで以下のコマンドを打つだけで**iPad上のアプリも自動的に最新版に更新**されます。

```powershell
git add .
git commit -m "Update features"
git push
```

