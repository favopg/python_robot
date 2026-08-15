import json
import os
import sys
import config
from katago_analyzer import KataGoAnalyzer, parse_sgf

def print_analysis_result(res):
    """解析結果のJSONを見やすくコンソールに出力します。"""
    if not res:
        print("No analysis result.")
        return
    
    if "error" in res:
        print(f"Error from KataGo: {res['error']}")
        return

    turn_number = res.get("turnNumber", 0)
    root_info = res.get("rootInfo", {})
    current_player = root_info.get("currentPlayer", "?")
    winrate = root_info.get("winrate", 0.0) * 100
    score_lead = root_info.get("scoreLead", 0.0)
    visits = root_info.get("visits", 0)

    print(f"\n=== Analysis (Turn: {turn_number}, Player: {current_player}) ===")
    print(f"Visits: {visits}")
    print(f"Winrate ({current_player}): {winrate:.1f}%")
    print(f"Score Lead: {score_lead:+.1f} pts")

    move_infos = res.get("moveInfos", [])
    if move_infos:
        print("\nTop Candidate Moves:")
        print(f"{'Rank':<5} {'Move':<6} {'Visits':<8} {'Winrate':<10} {'ScoreLead':<10} {'PV (Principal Variation)':<20}")
        print("-" * 65)
        for idx, m in enumerate(move_infos[:10], start=1):
            move = m.get("move", "")
            m_visits = m.get("visits", 0)
            m_winrate = m.get("winrate", 0.0) * 100
            m_lead = m.get("scoreLead", 0.0)
            pv_list = m.get("pv", [])
            pv = " ".join(pv_list[:3])
            print(f"{idx:<5} {move:<6} {m_visits:<8} {m_winrate:>5.1f}%     {m_lead:>+6.1f} pts  {pv}")
    print("=" * 65 + "\n")

def main():
    # 引数からSGFファイルのパスを取得、なければデフォルトを使用
    if len(sys.argv) > 1:
        sgf_file = sys.argv[1]
    else:
        sgf_file = os.path.join(config.SGF_DIR, "sample.sgf")
    
    if not os.path.exists(sgf_file):
        print(f"Error: {sgf_file} does not exist.")
        return

    analyzer = KataGoAnalyzer()
    
    # 0. 既存のログを削除
    analyzer.clear_logs()
    
    try:
        # 1. KataGo Analysis Engineの起動
        print("Starting KataGo Analysis Engine...")
        status = analyzer.start()
        print(f"KataGo Status: {status}")

        # 対話モード
        print("\n--- Analysis Engine Interactive Mode ---")
        print("Commands:")
        print("  auto               : Analyze the specified SGF file (final position)")
        print("  turns <N1,N2,...>  : Analyze specific turns in SGF (e.g. 'turns 0,1,2')")
        print("  sgf <path>         : Analyze another SGF file")
        print("  json <json_query>  : Send raw JSON query directly to KataGo")
        print("  exit               : Quit")
        
        # 最初に自動解析を実行
        print(f"\n[Auto Analysis] Analyzing SGF: {sgf_file}")
        parsed = parse_sgf(sgf_file)
        print(f"SGF Loaded: {len(parsed['moves'])} moves, Komi: {parsed['komi']}, Rules: {parsed['rules']}")
        res = analyzer.analyze_sgf(sgf_file, max_visits=100)
        print_analysis_result(res)

        while True:
            cmd = input("Analysis > ").strip()
            if not cmd:
                continue
            if cmd.lower() == 'exit':
                break
            elif cmd.lower() == 'auto':
                res = analyzer.analyze_sgf(sgf_file, max_visits=100)
                print_analysis_result(res)
            elif cmd.lower().startswith('turns '):
                parts = cmd[6:].split(',')
                try:
                    turns = [int(t.strip()) for t in parts if t.strip()]
                    results = analyzer.analyze_sgf(sgf_file, max_visits=100, analyze_turns=turns)
                    if isinstance(results, list):
                        for r in results:
                            print_analysis_result(r)
                    else:
                        print_analysis_result(results)
                except ValueError:
                    print("Invalid turn numbers. Example: turns 0, 1, 2")
            elif cmd.lower().startswith('sgf '):
                target_sgf = cmd[4:].strip()
                if os.path.exists(target_sgf):
                    res = analyzer.analyze_sgf(target_sgf, max_visits=100)
                    print_analysis_result(res)
                else:
                    print(f"File not found: {target_sgf}")
            elif cmd.lower().startswith('json '):
                raw_json = cmd[5:].strip()
                try:
                    q = json.loads(raw_json)
                    res = analyzer.query(q)
                    print(json.dumps(res, indent=2))
                except Exception as ex:
                    print(f"JSON query error: {ex}")
            else:
                print("Unknown command. Available commands: auto, turns <N1,N2>, sgf <path>, json <query>, exit")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # 終了
        print("Stopping KataGo Analysis Engine...")
        analyzer.stop()

if __name__ == "__main__":
    main()
