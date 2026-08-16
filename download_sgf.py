import sys
import os
import re
import json
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_url(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode('utf-8')

def sanitize_filename(name):
    clean = re.sub(r'[\\/*?:"<>|\s]+', '_', name).strip('_.')
    return clean if clean else "game"

def main():
    sgf_dir = os.path.join(os.getcwd(), 'sgf')
    os.makedirs(sgf_dir, exist_ok=True)
    
    # Collect game UUIDs across pages
    all_game_uuids = []
    seen_uuids = set()
    current_url = 'https://kifubara.app/ja/games'
    
    page = 1
    while current_url and len(all_game_uuids) < 100 and page <= 5:
        print(f"Fetching list page {page}: {current_url}")
        html = fetch_url(current_url)
        new_on_page = 0
        for m in re.finditer(r'/ja/games/([0-9a-fA-F-]{36})', html):
            gid = m.group(1)
            if gid not in seen_uuids:
                seen_uuids.add(gid)
                all_game_uuids.append(gid)
                new_on_page += 1
        
        print(f"Page {page} added {new_on_page} games. Total unique: {len(all_game_uuids)}")
        
        # Check next page link
        next_match = re.search(r'href="(\?page=\d+[^"]*)"', html)
        if next_match:
            next_qs = next_match.group(1).replace('&amp;', '&')
            current_url = urllib.parse.urljoin('https://kifubara.app/ja/games', next_qs)
            page += 1
        else:
            break

    print(f"Total game UUIDs collected across {page} pages: {len(all_game_uuids)}")

    def fetch_game_sgf(gid):
        g_url = f'https://kifubara.app/ja/games/{gid}'
        try:
            g_html = fetch_url(g_url)
            m = re.search(r'var\s+sgf\s*=\s*("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\');', g_html)
            if not m:
                return None
            sgf_content = json.loads(m.group(1))
            dt_match = re.search(r'DT\[([^\]]*)\]', sgf_content)
            dt = dt_match.group(1) if dt_match else ""
            
            pb_match = re.search(r'PB\[([^\]]*)\]', sgf_content)
            pw_match = re.search(r'PW\[([^\]]*)\]', sgf_content)
            pb = pb_match.group(1) if pb_match else "Black"
            pw = pw_match.group(1) if pw_match else "White"
            
            return {
                "uuid": gid,
                "date": dt,
                "black": pb,
                "white": pw,
                "sgf": sgf_content
            }
        except Exception as ex:
            return None

    # Fetch details concurrently
    print("Fetching game details in parallel...")
    results_by_index = {}
    with ThreadPoolExecutor(max_workers=12) as executor:
        future_to_index = {executor.submit(fetch_game_sgf, gid): idx for idx, gid in enumerate(all_game_uuids)}
        for future in as_completed(future_to_index):
            idx = future_to_index[future]
            res = future.result()
            if res:
                results_by_index[idx] = res

    # Sort in original chronological/listed order
    sorted_indices = sorted(results_by_index.keys())
    valid_202608_games = []
    for idx in sorted_indices:
        item = results_by_index[idx]
        dt = item["date"]
        # Match 2026-08 or 202608
        if dt.startswith("2026-08") or dt.startswith("202608"):
            valid_202608_games.append(item)
            if len(valid_202608_games) == 31:
                break

    print(f"Collected {len(valid_202608_games)} games from 2026-08.")

    # Clean existing sgf directory to have exactly 31 files
    for fname in os.listdir(sgf_dir):
        fpath = os.path.join(sgf_dir, fname)
        if os.path.isfile(fpath):
            os.remove(fpath)

    # Save exactly 31 files into sgf_dir
    saved_files = []
    for i, g in enumerate(valid_202608_games, start=1):
        dt_clean = g["date"].replace("-", "")
        b_clean = sanitize_filename(g["black"])
        w_clean = sanitize_filename(g["white"])
        filename = f"{dt_clean}_{i:02d}_{b_clean}_vs_{w_clean}_{g['uuid'][:8]}.sgf"
        filepath = os.path.join(sgf_dir, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(g["sgf"])
        saved_files.append((filename, g["date"], g["uuid"]))

    print(f"Successfully saved {len(saved_files)} SGF files to {sgf_dir}.")
    
    # Write index.json / report
    report = [
        {"file": f, "date": dt, "uuid": gid}
        for f, dt, gid in saved_files
    ]
    with open(os.path.join(sgf_dir, "sgf_index.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
