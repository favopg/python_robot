import os
import re
import glob
import json
import shutil
from datetime import datetime
import config
from katago_analyzer import KataGoAnalyzer, parse_sgf

def analyze_and_pickup():
    # 入力SGFフォルダ（当プロジェクトのsgfフォルダ）
    project_root = os.path.dirname(os.path.abspath(__file__))
    sgf_dir = os.path.join(project_root, "sgf")
    pickup_dir = os.path.join(project_root, "sgf_pickup")
    
    os.makedirs(pickup_dir, exist_ok=True)
    # 既存のsgf_pickupフォルダ内SGFファイルをクリア
    for fname in os.listdir(pickup_dir):
        fpath = os.path.join(pickup_dir, fname)
        if os.path.isfile(fpath) and fname.endswith('.sgf'):
            try:
                os.remove(fpath)
            except Exception:
                pass
    
    sys_month = datetime.now().strftime("%Y%m")
    
    # sgf直下のSGFファイル取得
    sgf_files = sorted(glob.glob(os.path.join(sgf_dir, "*.sgf")))
    print(f"Found {len(sgf_files)} SGF files in {sgf_dir}")
    if not sgf_files:
        print("No SGF files found.")
        return

    # KataGoアナライザー初期化 (maxVisits: 1000)
    analyzer = KataGoAnalyzer()
    analyzer.clear_logs()
    
    print("Starting KataGo Analysis Engine...")
    analyzer.start()
    
    picked_games = []
    
    try:
        for idx, filepath in enumerate(sgf_files, start=1):
            filename = os.path.basename(filepath)
            print(f"\n[{idx}/{len(sgf_files)}] Analyzing: {filename} ...")
            
            try:
                parsed = parse_sgf(filepath)
                komi = parsed.get("komi")
                if komi not in (6.5, 7.5):
                    print(f"  [SKIP] Komi is {komi} (not 6.5 or 7.5). Skipping {filename}...")
                    continue

                total_moves = len(parsed["moves"])
                # 有効手番範囲: 全手番 (0手目からtotal_moves手目まで)
                target_turns = list(range(0, total_moves + 1))
                
                # 解析実行 (maxVisits=1000)
                raw_results = analyzer.analyze_sgf(filepath, max_visits=1000, analyze_turns=target_turns)
                if not isinstance(raw_results, list):
                    raw_results = [raw_results]
            except Exception as e:
                print(f"  [ERROR] Analysis failed for {filename}: {e}")
                continue
                
            # turnNumber順にソート
            raw_results.sort(key=lambda r: r.get("turnNumber", 0))
            
            # 各手番の黒番基準勝率・目数リード、手番プレイヤー等の整理
            # KataGoのrootInfo:
            # - currentPlayer: 次に打つ手番 ('B' または 'W')
            # - winrate: currentPlayer視点の勝率 (0.0 〜 1.0)
            # - scoreLead: currentPlayer視点のリード目数 (+は優勢, -は劣勢)
            turn_records = {}
            for res in raw_results:
                t = res.get("turnNumber", 0)
                root = res.get("rootInfo", {})
                player = root.get("currentPlayer", "B")
                p_winrate = root.get("winrate", 0.5)
                p_lead = root.get("scoreLead", 0.0)
                
                # 黒基準(Black)の勝率および目数リードに換算
                b_winrate = p_winrate if player == "B" else (1.0 - p_winrate)
                b_lead = p_lead if player == "B" else -p_lead
                
                turn_records[t] = {
                    "turn": t,
                    "player": player,
                    "p_winrate": p_winrate,
                    "p_lead": p_lead,
                    "b_winrate": b_winrate,
                    "b_lead": b_lead
                }
            
            # 条件判定
            # ① 1手ごとの勝率急落幅（Winrate Drop）: 30%以上の下落が存在するか (winrate_drop >= 0.30)
            # ② 目数損失幅（Score Loss）: 6目以上の損失が存在するか (score_loss >= 6.0)
            # ③ 逆転局面（Turnaround / Lead Flip）: 勝率が70%以上（優勢）の側が一気に40%以下（劣勢）へ転落した局面が存在するか
            
            cond1_hits = []
            cond2_hits = []
            cond3_hits = []
            
            for t in range(1, total_moves + 1):
                if (t - 1) not in turn_records or t not in turn_records:
                    continue
                prev = turn_records[t - 1]
                curr = turn_records[t]
                
                # t手目を打ったプレイヤー
                # prev["player"] がその手番を打ったプレイヤー
                played_player = prev["player"]
                
                # 着手前の着手側勝率・リード
                winrate_before = prev["p_winrate"] # 着手側から見た勝率 (0.0~1.0)
                lead_before = prev["p_lead"]       # 着手側から見たリード目数
                
                # 着手後の着手側勝率・リード
                # currの currentPlayer は相手側なので、着手側から見ると 1.0 - curr["p_winrate"], -curr["p_lead"]
                winrate_after = 1.0 - curr["p_winrate"]
                lead_after = -curr["p_lead"]
                
                # 損失計算 (着手前 - 着手後)
                winrate_drop = winrate_before - winrate_after
                score_loss = lead_before - lead_after
                
                # ① 勝率急落幅: 30%以上 (0.30 <= winrate_drop)
                if winrate_drop >= 0.30:
                    cond1_hits.append({
                        "turn": t,
                        "player": played_player,
                        "winrate_drop": round(winrate_drop * 100, 2),
                        "winrate_before": round(winrate_before * 100, 2),
                        "winrate_after": round(winrate_after * 100, 2)
                    })
                    
                # ② 目数損失幅: 6目以上の損失 (score_loss >= 6.0)
                if score_loss >= 6.0:
                    cond2_hits.append({
                        "turn": t,
                        "player": played_player,
                        "score_loss": round(score_loss, 2),
                        "lead_before": round(lead_before, 2),
                        "lead_after": round(lead_after, 2)
                    })
                    
                # ③ 逆転局面: 着手前70%以上だったのが着手後40%以下へ転落
                if winrate_before >= 0.70 and winrate_after <= 0.40:
                    cond3_hits.append({
                        "turn": t,
                        "player": played_player,
                        "winrate_before": round(winrate_before * 100, 2),
                        "winrate_after": round(winrate_after * 100, 2)
                    })
            
            is_matched = bool(cond1_hits or cond2_hits or cond3_hits)
            
            if is_matched:
                seq = len(picked_games) + 1
                black_name = parsed.get("black", "Black")
                white_name = parsed.get("white", "White")
                b_clean = re.sub(r'[\\/*?:"<>|\s]+', '_', black_name).strip('_.') or "Black"
                w_clean = re.sub(r'[\\/*?:"<>|\s]+', '_', white_name).strip('_.') or "White"
                
                new_filename = f"{sys_month}{seq:02d}_{b_clean}VS{w_clean}.sgf"
                dest_path = os.path.join(pickup_dir, new_filename)
                shutil.copy2(filepath, dest_path)
                
                print(f"  -> MATCHED! [{seq:02d}/31] Saved as: {new_filename}")
                print(f"     Cond1 (WinrateDrop>=30%): {len(cond1_hits)}, Cond2 (ScoreLoss>=6): {len(cond2_hits)}, Cond3 (Turnaround 70%->40%): {len(cond3_hits)}")
                
                picked_games.append({
                    "file": new_filename,
                    "original_file": filename,
                    "seq": seq,
                    "black": b_clean,
                    "white": w_clean,
                    "total_moves": total_moves,
                    "cond1_count": len(cond1_hits),
                    "cond2_count": len(cond2_hits),
                    "cond3_count": len(cond3_hits),
                    "cond1_details": cond1_hits[:5], # 上位/一部抜粋
                    "cond2_details": cond2_hits[:5],
                    "cond3_details": cond3_hits[:5]
                })
                
                if len(picked_games) >= 31:
                    print(f"\n31件のSGFファイルをピックアップ完了しました。処理を終了します。")
                    break
            else:
                print(f"  -> No conditions matched.")
                
    finally:
        print("\nStopping KataGo...")
        analyzer.stop()
        
    print(f"\n==========================================")
    print(f"Analysis Finished!")
    print(f"Total SGF analyzed: {len(sgf_files)}")
    print(f"Total SGF picked up: {len(picked_games)}")
    print(f"Saved to: {pickup_dir}")
    print(f"==========================================")
    
    # レポートJSON出力
    report_file = os.path.join(pickup_dir, "pickup_report.json")
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(picked_games, f, ensure_ascii=False, indent=2)
    print(f"Report written to {report_file}")

if __name__ == "__main__":
    analyze_and_pickup()
