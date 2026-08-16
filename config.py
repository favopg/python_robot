import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# KataGo settings
KATAGO_PATH = os.path.join(BASE_DIR, "katago", "katago.exe")
MODEL_PATH = os.path.join(BASE_DIR, "katago", "kata1-b10c128-s41138688-d27396855.txt.gz")
CONFIG_PATH = os.path.join(BASE_DIR, "katago", "default_gtp.cfg")
SGF_DIR = os.path.join(BASE_DIR, "sgf")
