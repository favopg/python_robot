import os
import platform

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# KataGo settings
if platform.system() == "Windows":
    KATAGO_PATH = os.path.join(BASE_DIR, "katago", "katago.exe")
else:
    KATAGO_PATH = os.path.join(BASE_DIR, "katago", "katago")
MODEL_PATH = os.path.join(BASE_DIR, "katago", "kata1-b28c512nbt-s7168446720-d4316919285.bin.gz")
CONFIG_PATH = os.path.join(BASE_DIR, "katago", "default_gtp.cfg")
SGF_DIR = os.path.join(BASE_DIR, "sgf")
