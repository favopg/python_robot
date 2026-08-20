import os
import re
import ssl
import urllib.request

GAMES = [
    ("020609.sgf", "https://homepages.cwi.nl/~aeb/go/games/games/other_sizes/9x9/Minigo/020609.sgf"),
    ("020616.sgf", "https://homepages.cwi.nl/~aeb/go/games/games/other_sizes/9x9/Minigo/020616.sgf"),
    ("020623.sgf", "https://homepages.cwi.nl/~aeb/go/games/games/other_sizes/9x9/Minigo/020623.sgf"),
    ("020630.sgf", "https://homepages.cwi.nl/~aeb/go/games/games/other_sizes/9x9/Minigo/020630.sgf"),
    ("020602.sgf", "https://homepages.cwi.nl/~aeb/go/games/games/other_sizes/9x9/Minigo/020602.sgf"),
]

def sanitize_filename(name):
    clean = re.sub(r'[\\/*?:"<>|\s]+', '_', name).strip('_.')
    return clean if clean else "unknown"

def main():
    sgf9_dir = os.path.join(os.getcwd(), 'sgf9')
    os.makedirs(sgf9_dir, exist_ok=True)
    
    ctx = ssl._create_unverified_context()
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    saved = 0
    for idx, (base_name, url) in enumerate(GAMES, 1):
        print(f"[{idx}/5] ダウンロード中: {url}")
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            content = resp.read().decode('utf-8', errors='replace')
        
        # SGFヘッダー情報の抽出
        pb_match = re.search(r'PB\[(.*?)\]', content)
        pw_match = re.search(r'PW\[(.*?)\]', content)
        dt_match = re.search(r'DT\[(.*?)\]', content)
        sz_match = re.search(r'SZ\[(.*?)\]', content)
        
        black_name = sanitize_filename(pb_match.group(1)) if pb_match else "Black"
        white_name = sanitize_filename(pw_match.group(1)) if pw_match else "White"
        date_str = sanitize_filename(dt_match.group(1).replace('-', '')) if dt_match else "unknown"
        board_size = sz_match.group(1) if sz_match else "unknown"
        
        filename = f"{idx:03d}_{date_str}_{black_name}_vs_{white_name}.sgf"
        filepath = os.path.join(sgf9_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
            
        print(f"  -> 保存完了: {filename} (SZ: {board_size})")
        saved += 1
        
    print(f"\n合計 {saved} 局の9路盤SGFファイルを {sgf9_dir} に保存しました。")

if __name__ == "__main__":
    main()
