import sys
import os
import json
import config
from katago_analyzer import KataGoAnalyzer, parse_sgf

def parse_turn_range(range_str, max_available_turns=None):
    """
    手番範囲の文字列をパースして手番（整数）のリストを返します。
    例:
      '0-50' -> [0, 1, ..., 50]
      '0..50' -> [0, 1, ..., 50]
      '10' -> [0, 1, ..., 10]
      '0,5,10' -> [0, 5, 10]
    """
    range_str = range_str.strip()
    if "-" in range_str:
        parts = range_str.split("-", 1)
        start = int(parts[0].strip())
        end = int(parts[1].strip())
        return list(range(start, end + 1))
    elif ".." in range_str:
        parts = range_str.split("..", 1)
        start = int(parts[0].strip())
        end = int(parts[1].strip())
        return list(range(start, end + 1))
    elif "," in range_str:
        return [int(x.strip()) for x in range_str.split(",") if x.strip()]
    else:
        # 単一数値指定の場合は 0 からその手数まで
        val = int(range_str)
        return list(range(0, val + 1))

def analyze_sgf_range(sgf_path, turn_range_str="0-50", max_visits=100, output_json=False):
    """
    SGFファイルと局面範囲（例: '0-50'）を指定して解析を実行します。
    """
    if not os.path.exists(sgf_path):
        print(f"Error: SGF file not found at '{sgf_path}'")
        return

    parsed = parse_sgf(sgf_path)
    total_moves = len(parsed["moves"])
    
    turns = parse_turn_range(turn_range_str, max_available_turns=total_moves)
    # SGFの手数を超える手番は除外（0手目〜total_moves手目までが有効）
    valid_turns = [t for t in turns if 0 <= t <= total_moves]
    
    if not valid_turns:
        print(f"Error: No valid turns specified. SGF has {total_moves} moves (valid turns: 0 to {total_moves}).")
        return

    print(f"============================================================")
    print(f" SGF File    : {sgf_path}")
    print(f" Total Moves : {total_moves}")
    print(f" Target Turns: {valid_turns[0]} to {valid_turns[-1]} (Total {len(valid_turns)} positions)")
    print(f" Visits/pos  : {max_visits}")
    print(f" Rules/Komi  : {parsed['rules']} / {parsed['komi']}")
    print(f"============================================================\n")

    analyzer = KataGoAnalyzer()
    analyzer.clear_logs()

    try:
        analyzer.start()
        print("KataGo Analysis Engine started. Running analysis...\n")

        results = analyzer.analyze_sgf(sgf_path, max_visits=max_visits, analyze_turns=valid_turns)
        if not isinstance(results, list):
            results = [results]

        if output_json:
            print(json.dumps(results, indent=2))
            return

        # ヘッダー表示
        header = f"{'Turn':<6} {'Plyr':<5} {'Winrate':<10} {'ScoreLead':<12} {'BestMove':<9} {'PV (Principal Variation)'}"
        print(header)
        print("-" * 80)

        for res in results:
            turn = res.get("turnNumber", 0)
            root_info = res.get("rootInfo", {})
            player = root_info.get("currentPlayer", "?")
            winrate = root_info.get("winrate", 0.0) * 100
            score_lead = root_info.get("scoreLead", 0.0)

            move_infos = res.get("moveInfos", [])
            if move_infos:
                best_move = move_infos[0].get("move", "None")
                pv_list = move_infos[0].get("pv", [])
                pv_str = " ".join(pv_list[:3]) + (" ..." if len(pv_list) > 3 else "")
            else:
                best_move = "None"
                pv_str = ""

            # 手番ごとの結果を出力
            print(f"{turn:<6d} {player:<5} {winrate:>5.1f}%     {score_lead:>+6.1f} pts    {best_move:<9} {pv_str}")

        print("-" * 80)
        print(f"Analysis completed successfully ({len(results)} positions).")

    finally:
        analyzer.stop()

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="SGF棋譜の指定手番範囲（例: 0-50）を一括解析するスクリプト",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "sgf_path",
        nargs="?",
        default=os.path.join(config.SGF_DIR, "sample.sgf"),
        help="解析対象のSGFファイルパス (デフォルト: C:\\katago\\sgf\\sample.sgf)"
    )
    parser.add_argument(
        "turn_range",
        nargs="?",
        default="0-50",
        help="解析対象の手番範囲 (例: '0-50', '0..30', '10,20,30', デフォルト: '0-50')"
    )
    parser.add_argument(
        "--visits", "-v",
        type=int,
        default=100,
        help="各局面の探索手数 (maxVisits, デフォルト: 100)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="結果を生のJSON形式で出力"
    )

    args = parser.parse_args()
    analyze_sgf_range(
        sgf_path=args.sgf_path,
        turn_range_str=args.turn_range,
        max_visits=args.visits,
        output_json=args.json
    )

if __name__ == "__main__":
    main()
