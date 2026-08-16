import os
import re
import html
import time
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_url(url, retries=3):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    req = urllib.request.Request(url, headers=headers)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read().decode('utf-8')
        except Exception as e:
            if attempt == retries - 1:
                raise e
            time.sleep(1)

def sanitize_filename(name):
    clean = re.sub(r'[\\/*?:"<>|\s]+', '_', name).strip('_.')
    return clean if clean else "unknown"

def collect_latest_game_ids(target_count=100):
    game_ids = []
    seen = set()
    page = 1
    
    while len(game_ids) < target_count:
        list_url = f"https://kifudepot.net/index.php?page={page}"
        print(f"一覧取得中 (Page {page}): {list_url}")
        page_html = fetch_url(list_url)
        
        matches = re.findall(r'kifucontents\.php\?id=([a-zA-Z0-9%_\-\+\=]+)', page_html)
        if not matches:
            print(f"Page {page} で対局リンクが見つかりませんでした。")
            break
            
        new_count = 0
        for gid in matches:
            if gid not in seen:
                seen.add(gid)
                game_ids.append(gid)
                new_count += 1
                if len(game_ids) >= target_count:
                    break
                    
        print(f"Page {page} から {new_count} 件追加 (合計: {len(game_ids)}/{target_count})")
        page += 1
        time.sleep(0.5)
        
    return game_ids[:target_count]

def fetch_game_sgf(game_id, index):
    game_url = f"https://kifudepot.net/kifucontents.php?id={game_id}"
    try:
        game_html = fetch_url(game_url)
        match = re.search(r'<textarea\s+id\s*=\s*["\']sgf["\'][^>]*>(.*?)</textarea>', game_html, re.DOTALL)
        if not match:
            print(f"[{index:03d}] SGFタグが見つかりませんでした: {game_url}")
            return None
            
        sgf_text = html.unescape(match.group(1).strip())
        if not sgf_text.startswith("(;"):
            print(f"[{index:03d}] SGFフォーマット不正: {game_url}")
            return None
            
        pb_match = re.search(r'PB\[(.*?)\]', sgf_text)
        pw_match = re.search(r'PW\[(.*?)\]', sgf_text)
        dt_match = re.search(r'DT\[(.*?)\]', sgf_text)
        
        black_name = pb_match.group(1) if pb_match else "Black"
        white_name = pw_match.group(1) if pw_match else "White"
        date_str = dt_match.group(1).replace('-', '') if dt_match else "unknown"
        
        return {
            "index": index,
            "id": game_id,
            "date": date_str,
            "black": black_name,
            "white": white_name,
            "sgf": sgf_text
        }
    except Exception as e:
        print(f"[{index:03d}] エラー ({game_url}): {e}")
        return None

def main():
    target_count = 100
    sgf_dir = os.path.join(os.getcwd(), 'sgf')
    os.makedirs(sgf_dir, exist_ok=True)
    
    # 既存のsgfディレクトリ内ファイルをクリア（必要に応じて）
    for fname in os.listdir(sgf_dir):
        fpath = os.path.join(sgf_dir, fname)
        if os.path.isfile(fpath) and fname.endswith('.sgf'):
            os.remove(fpath)
            
    print(f"最新 {target_count} 件の対局IDを取得中...")
    game_ids = collect_latest_game_ids(target_count)
    print(f"取得完了: {len(game_ids)} 件")
    
    print("SGFデータのダウンロード中 (並列処理)...")
    results = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(fetch_game_sgf, gid, idx + 1): idx + 1 for idx, gid in enumerate(game_ids)}
        for future in as_completed(futures):
            res = future.result()
            if res:
                results[res["index"]] = res
                
    saved_count = 0
    for idx in sorted(results.keys()):
        item = results[idx]
        b_clean = sanitize_filename(item["black"])
        w_clean = sanitize_filename(item["white"])
        date_clean = sanitize_filename(item["date"])
        
        filename = f"{item['index']:03d}_{date_clean}_{b_clean}_vs_{w_clean}.sgf"
        filepath = os.path.join(sgf_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(item["sgf"])
        saved_count += 1
        
    print(f"\n==========================================")
    print(f"正常に保存されたSGFファイル数: {saved_count} / {target_count}")
    print(f"保存先: {sgf_dir}")
    print(f"==========================================")

if __name__ == "__main__":
    main()
