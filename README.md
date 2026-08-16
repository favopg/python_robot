# 囲碁AI KataGoを利用した問題作成ツール

KataGoの **Analysis Engine モード** を利用してSGF棋譜の局面解析や最善手・勝率・目数差の取得を行います。

## 環境構築
1. 仮想環境の有効化:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```
2. 依存パッケージのインストール:
   ```bash
   pip install -r requirements.txt
   ```

## 設定
`config.py` にKataGoの実行ファイルパス、モデルファイルパス、設定ファイルパス、SGFディレクトリパスが記述されています。

## 使い方
1. KataGoの疎通確認:
   ```powershell
   .\.venv\Scripts\python.exe check_katago.py
   ```
2. メイン解析プログラム（Analysis Engine）の実行:
   ```powershell
   # デフォルトのSGF (sample.sgf) を使用する場合
   .\.venv\Scripts\python.exe main.py
   
   # 特定のSGFファイルを指定する場合
   .\.venv\Scripts\python.exe main.py .\sgf\target.sgf
   ```

3. 対話モードでのコマンド:
   - `auto`: 指定したSGFファイルの最終局面を解析します。
   - `turns <0,1,2,...>`: SGFファイル内の指定した手番局面を解析します。
   - `sgf <path>`: 別のSGFファイルを指定して解析します。
   - `json <query>`: KataGo Analysis Engine形式のJSONクエリを直接送信します。
   - `exit`: プログラムを終了します。

### ログについて
`main.py` を実行すると、`gtp_logs` および `analysis_logs` ディレクトリ内の既存のログファイルは自動的にクリーンアップされます。

### タイムアウトについて
KataGoの大きなモデル（bin.gz）を読み込む際、GPUの初期化やチューニングで初回に時間がかかる場合があります。
当プロジェクトのプログラムは、KataGoの初期化および解析応答を適切に待機するように設計されています。
