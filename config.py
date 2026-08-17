import os
import platform

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# KataGo settings
if platform.system() == "Windows":
    KATAGO_PATH = os.path.join(BASE_DIR, "katago", "katago.exe")
else:
    KATAGO_PATH = os.path.join(BASE_DIR, "katago", "katago")
MODEL_PATH = os.path.join(BASE_DIR, "katago", "kata1-b10c128-s41138688-d27396855.txt.gz")
CONFIG_PATH = os.path.join(BASE_DIR, "katago", "default_gtp.cfg")
SGF_DIR = os.path.join(BASE_DIR, "sgf")
