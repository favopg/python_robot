import os
import subprocess
import config

def check_katago():
    print(f"Checking KataGo at: {config.KATAGO_PATH}")
    print(f"Model exists ({config.MODEL_PATH}): {os.path.exists(config.MODEL_PATH)}")
    print(f"Config exists ({config.CONFIG_PATH}): {os.path.exists(config.CONFIG_PATH)}")
    try:
        # KataGoのバージョン確認
        process = subprocess.Popen(
            [config.KATAGO_PATH, "version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate()
        print("KataGo Output:")
        print(stdout)
        if stderr:
            print("KataGo Errors:")
            print(stderr)
    except Exception as e:
        print(f"Error running KataGo: {e}")

if __name__ == "__main__":
    check_katago()
