import os
import time
import config
from katago_analyzer import KataGoAnalyzer

def debug_search_analyze():
    analyzer = KataGoAnalyzer()
    print("Starting KataGo...")
    try:
        analyzer.start()
        
        sgf_file = os.path.join(config.SGF_DIR, "sample.sgf")
        if os.path.exists(sgf_file):
            print(f"Loading {sgf_file}")
            analyzer.load_sgf(sgf_file)
        
        command = "kata-search_analyze interval 100\n"
        print(f"Sending: {command.strip()}")
        
        analyzer.process.stdin.write(command)
        analyzer.process.stdin.flush()
        
        print("Reading response (first 10 lines or 5 seconds)...")
        start_time = time.time()
        lines_read = 0
        while lines_read < 20 and time.time() - start_time < 5:
            line = analyzer.process.stdout.readline()
            if line:
                print(f"OUT: {repr(line)}")
                lines_read += 1
            else:
                time.sleep(0.1)
                
    except Exception as e:
        print(f"Error: {e}")
    finally:
        analyzer.stop()

if __name__ == '__main__':
    debug_search_analyze()