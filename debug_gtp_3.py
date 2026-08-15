import os
import sys
import time
import config
from katago_analyzer import KataGoAnalyzer

def debug_search_analyze():
    analyzer = KataGoAnalyzer()
    # stderrをキャプチャして表示するように一時的に修正
    print("Starting KataGo...")
    try:
        analyzer.start()
        
        # モデル読み込み待ちなどのために少し待つ
        time.sleep(2)
        
        command = "kata-search_analyze interval 100\n"
        print(f"Sending: {command.strip()}")
        
        analyzer.process.stdin.write(command)
        analyzer.process.stdin.flush()
        
        print("Reading stdout/stderr...")
        # タイムアウト付きで読み取る
        import threading
        def read_stream(stream, name):
            while True:
                line = stream.readline()
                if not line: break
                print(f"{name}: {line.strip()}")

        t1 = threading.Thread(target=read_stream, args=(analyzer.process.stdout, "STDOUT"))
        t2 = threading.Thread(target=read_stream, args=(analyzer.process.stderr, "STDERR"))
        t1.daemon = True
        t2.daemon = True
        t1.start()
        t2.start()
        
        time.sleep(10)
        print("Done waiting.")
                
    except Exception as e:
        print(f"Error: {e}")
    finally:
        print("Stopping...")
        analyzer.stop()

if __name__ == '__main__':
    debug_search_analyze()