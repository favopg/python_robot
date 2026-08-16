import json
import os
import re
import shutil
import subprocess
import threading
import time
import config

def coord_to_gtp(pos, board_x_size=19, board_y_size=19):
    """SGF座標（例: 'pd'）をGTP座標（例: 'Q16'）に変換します。"""
    if not pos or pos.lower() == "tt" or pos == "":
        return "pass"
    pos = pos.lower()
    if len(pos) < 2:
        return "pass"
    x = ord(pos[0]) - ord('a')
    y = ord(pos[1]) - ord('a')
    if x < 0 or x >= board_x_size or y < 0 or y >= board_y_size:
        return "pass"
    gtp_cols = "ABCDEFGHJKLMNOPQRSTUVWXYZ"
    col_str = gtp_cols[x]
    row_str = str(board_y_size - y)
    return f"{col_str}{row_str}"

def gtp_to_coord(gtp_pos, board_x_size=19, board_y_size=19):
    """GTP座標（例: 'Q16'）をSGF座標（例: 'pd'）に変換します。"""
    if not gtp_pos or gtp_pos.lower() == "pass":
        return ""
    gtp_pos = gtp_pos.upper().strip()
    if len(gtp_pos) < 2:
        return ""
    gtp_cols = "ABCDEFGHJKLMNOPQRSTUVWXYZ"
    col_char = gtp_pos[0]
    if col_char not in gtp_cols:
        return ""
    x = gtp_cols.index(col_char)
    try:
        row_num = int(gtp_pos[1:])
    except ValueError:
        return ""
    y = board_y_size - row_num
    if x < 0 or x >= board_x_size or y < 0 or y >= board_y_size:
        return ""
    return f"{chr(ord('a') + x)}{chr(ord('a') + y)}"

def parse_sgf(sgf_text_or_path):
    """SGFファイルパスまたはSGF文字列をパースし、KataGo Analysis用の辞書を返します。"""
    if os.path.exists(sgf_text_or_path):
        with open(sgf_text_or_path, "r", encoding="utf-8", errors="ignore") as f:
            sgf_text = f.read()
    else:
        sgf_text = sgf_text_or_path

    board_size = 19
    komi = 6.5
    rules = "japanese"
    initial_stones = []
    initial_player = "B"
    moves = []

    sz_match = re.search(r'SZ\[(\d+)\]', sgf_text)
    if sz_match:
        board_size = int(sz_match.group(1))

    km_match = re.search(r'KM\[([\d\.]+)\]', sgf_text)
    if km_match:
        komi = float(km_match.group(1))

    ru_match = re.search(r'RU\[([^\]]+)\]', sgf_text, re.IGNORECASE)
    if ru_match:
        rules = ru_match.group(1).lower()

    pl_match = re.search(r'PL\[([BWbw])\]', sgf_text)
    if pl_match:
        initial_player = pl_match.group(1).upper()

    pb_match = re.search(r'PB\[([^\]]*)\]', sgf_text)
    pw_match = re.search(r'PW\[([^\]]*)\]', sgf_text)
    black_player = pb_match.group(1).strip() if pb_match else "Black"
    white_player = pw_match.group(1).strip() if pw_match else "White"

    # 置石（AB/AW）
    for m in re.finditer(r'AB((?:\[[a-zA-Z]{0,2}\])+)', sgf_text):
        for loc in re.findall(r'\[([a-zA-Z]{0,2})\]', m.group(1)):
            coord = coord_to_gtp(loc, board_size, board_size)
            if coord != "pass":
                initial_stones.append(["B", coord])
    for m in re.finditer(r'AW((?:\[[a-zA-Z]{0,2}\])+)', sgf_text):
        for loc in re.findall(r'\[([a-zA-Z]{0,2})\]', m.group(1)):
            coord = coord_to_gtp(loc, board_size, board_size)
            if coord != "pass":
                initial_stones.append(["W", coord])

    # 手番（B/W）
    move_matches = re.finditer(r';\s*([BWbw])\s*\[\s*([a-zA-Z]{0,2})\s*\]', sgf_text)
    for m in move_matches:
        player = m.group(1).upper()
        pos = m.group(2)
        coord = coord_to_gtp(pos, board_size, board_size)
        moves.append([player, coord])

    return {
        "boardXSize": board_size,
        "boardYSize": board_size,
        "komi": komi,
        "rules": rules,
        "initialStones": initial_stones,
        "initialPlayer": initial_player,
        "moves": moves,
        "black": black_player,
        "white": white_player
    }

class KataGoAnalyzer:
    def __init__(self, katago_path=None, model_path=None, config_path=None, override_config=None):
        self.katago_path = katago_path or config.KATAGO_PATH
        self.model_path = model_path or config.MODEL_PATH
        self.config_path = config_path or config.CONFIG_PATH
        self.override_config = override_config
        self.process = None
        self._stderr_thread = None

    def clear_logs(self):
        """gtp_logs および analysis_logs ディレクトリ内のファイルをすべて削除します。"""
        log_dirs = [
            os.path.join(os.getcwd(), "gtp_logs"),
            os.path.join(os.getcwd(), "analysis_logs")
        ]
        for log_dir in log_dirs:
            if os.path.exists(log_dir):
                print(f"Clearing logs in {log_dir}...")
                for filename in os.listdir(log_dir):
                    file_path = os.path.join(log_dir, filename)
                    try:
                        if os.path.isfile(file_path) or os.path.islink(file_path):
                            os.unlink(file_path)
                        elif os.path.isdir(file_path):
                            shutil.rmtree(file_path)
                    except Exception as e:
                        print(f"Failed to delete {file_path}. Reason: {e}")
            else:
                os.makedirs(log_dir, exist_ok=True)

    def _build_cmd(self):
        cmd = [
            self.katago_path,
            "analysis",
            "-model", self.model_path,
            "-config", self.config_path
        ]
        
        # default_gtp.cfg のように numAnalysisThreads が未定義の設定ファイルでも
        # 起動できるように override-config を付与
        overrides = []
        if self.override_config:
            overrides.append(self.override_config)
        
        # 設定ファイルに numAnalysisThreads や nnMaxBatchSize が含まれていない場合のフォールバック
        needs_analysis_params = True
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    if "numAnalysisThreads" in content and "nnMaxBatchSize" in content:
                        needs_analysis_params = False
            except Exception:
                pass
        
        if needs_analysis_params and not self.override_config:
            overrides.append("numAnalysisThreads=2,nnMaxBatchSize=64")

        for override in overrides:
            cmd.extend(["-override-config", override])

        return cmd

    def start(self):
        """KataGoをAnalysis Engineモードで起動します。"""
        cmd = self._build_cmd()
        print(f"Starting KataGo Analysis Engine: {' '.join(cmd)}")
        self.process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1
        )
        
        self.stderr_lines = []
        def _drain_stderr():
            try:
                for line in iter(self.process.stderr.readline, ''):
                    if not line:
                        break
                    self.stderr_lines.append(line)
                    if len(self.stderr_lines) > 100:
                        self.stderr_lines.pop(0)
            except Exception:
                pass

        self._stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
        self._stderr_thread.start()
        
        # 初回起動・モデル読み込み確認用プローブクエリ
        probe_query = {
            "id": "probe_init",
            "rules": "japanese",
            "komi": 6.5,
            "boardXSize": 19,
            "boardYSize": 19,
            "maxVisits": 1,
            "moves": []
        }
        res = self.query(probe_query)
        if "error" in res:
            raise RuntimeError(f"KataGo startup error: {res['error']}")
        return "KataGo Analysis Engine is ready."

    def is_running(self):
        """KataGoプロセスが動作中かどうかを判定します。"""
        return self.process is not None and self.process.poll() is None

    def stop(self):
        """KataGoプロセスを終了します。"""
        if self.process:
            try:
                if self.process.stdin:
                    self.process.stdin.close()
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None

    def query(self, query_dict):
        """KataGo Analysis EngineにJSONクエリを送信し、単一のレスポンスを取得します。"""
        if not self.process or self.process.poll() is not None:
            raise RuntimeError("KataGo process is not running.")

        query_str = json.dumps(query_dict)
        self.process.stdin.write(query_str + "\n")
        self.process.stdin.flush()

        line = self.process.stdout.readline()
        if not line:
            stderr_out = ""
            if self.process.stderr:
                try:
                    stderr_out = self.process.stderr.read()
                except Exception:
                    pass
            raise RuntimeError(f"KataGo stdout closed unexpectedly. stderr: {stderr_out}")

        return json.loads(line)

    def query_multi_turns(self, query_dict, turns_count=None):
        """複数手番の解析レスポンスを取得します。"""
        if not self.process or self.process.poll() is not None:
            raise RuntimeError("KataGo process is not running.")

        if turns_count is None:
            if "analyzeTurns" in query_dict:
                turns_count = len(query_dict["analyzeTurns"])
            elif "moves" in query_dict:
                turns_count = len(query_dict["moves"]) + 1
            else:
                turns_count = 1

        query_str = json.dumps(query_dict)
        self.process.stdin.write(query_str + "\n")
        self.process.stdin.flush()

        results = []
        for _ in range(turns_count):
            line = self.process.stdout.readline()
            if not line:
                break
            data = json.loads(line)
            if "error" in data:
                raise RuntimeError(f"KataGo error: {data['error']} (field: {data.get('field', 'unknown')})")
            results.append(data)

        return results

    def analyze_moves(self, moves, max_visits=100, rules="japanese", komi=6.5, board_size=19,
                      initial_stones=None, initial_player="B", analyze_turns=None, query_id=None,
                      extra_options=None):
        """着手シーケンスから解析クエリを構築して実行します。"""
        qid = query_id or f"query_{int(time.time() * 1000)}"
        query = {
            "id": qid,
            "rules": rules,
            "komi": komi,
            "boardXSize": board_size if isinstance(board_size, int) else board_size[0],
            "boardYSize": board_size if isinstance(board_size, int) else board_size[1],
            "maxVisits": max_visits,
            "moves": moves
        }
        if initial_stones:
            query["initialStones"] = initial_stones
        if initial_player:
            query["initialPlayer"] = initial_player
        if analyze_turns is not None:
            query["analyzeTurns"] = analyze_turns
        if extra_options:
            query.update(extra_options)

        if analyze_turns is not None and len(analyze_turns) > 1:
            return self.query_multi_turns(query, turns_count=len(analyze_turns))
        return self.query(query)

    def analyze_sgf(self, sgf_path_or_text, max_visits=100, analyze_turns=None, query_id=None, extra_options=None):
        """SGFファイルを読み込んで解析を実行します。"""
        parsed = parse_sgf(sgf_path_or_text)
        qid = query_id or f"sgf_{int(time.time() * 1000)}"
        
        query = {
            "id": qid,
            "rules": parsed["rules"],
            "komi": parsed["komi"],
            "boardXSize": parsed["boardXSize"],
            "boardYSize": parsed["boardYSize"],
            "maxVisits": max_visits,
            "moves": parsed["moves"]
        }
        if parsed.get("initialStones"):
            query["initialStones"] = parsed["initialStones"]
        if parsed.get("initialPlayer"):
            query["initialPlayer"] = parsed["initialPlayer"]
        if analyze_turns is not None:
            query["analyzeTurns"] = analyze_turns
        if extra_options:
            query.update(extra_options)

        if analyze_turns is not None and len(analyze_turns) > 1:
            return self.query_multi_turns(query, turns_count=len(analyze_turns))
        return self.query(query)

if __name__ == "__main__":
    analyzer = KataGoAnalyzer()
    try:
        print(analyzer.start())
        res = analyzer.analyze_moves([["B", "Q16"], ["W", "D4"]], max_visits=10)
        print("Analysis result:", json.dumps(res, indent=2))
    finally:
        analyzer.stop()
