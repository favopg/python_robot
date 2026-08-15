import os
import time
import config
from katago_analyzer import KataGoAnalyzer

def debug_search_analyze():
    analyzer = KataGoAnalyzer()
    print("Starting KataGo...")
    try:
        analyzer.start()
        
        # SGFがない場合に備えて盤面を少し進める
        analyzer.send_command("play B Q16")
        
        command = "kata-search_analyze interval 100\n"
        print(f"Sending: {command.strip()}")
        
        analyzer.process.stdin.write(command)
        analyzer.process.stdin.flush()
        
        print("Reading response...")
        # read() はブロックするので readline() を使うが、
        # そもそも '=' が返ってこない可能性を確認する
        for i in range(10):
            line = analyzer.process.stdout.readline()
            print(f"L{i}: {repr(line)}")
            if not line: break
                
    except Exception as e:
        print(f"Error: {e}")
    finally:
        print("Stopping...")
        analyzer.stop()

if __name__ == '__main__':
    debug_search_analyze()