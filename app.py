import glob
import hashlib
import json
import os
from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn

import config
from katago_analyzer import KataGoAnalyzer, parse_sgf
from analyze_range import parse_turn_range

# KataGoアナライザーのインスタンス
analyzer = KataGoAnalyzer()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPIアプリケーションのライフサイクル管理（KataGoの起動と停止）"""
    print("[INFO] Starting KataGo analysis engine...")
    analyzer.start()
    print("[INFO] KataGo analysis engine started successfully.")
    yield
    print("[INFO] Stopping KataGo analysis engine...")
    analyzer.stop()
    print("[INFO] KataGo analysis engine stopped.")

app = FastAPI(
    title="KataGo SGF Analysis API",
    description="Spring Boot連携用のKataGo解析APIサーバー",
    version="1.0.0",
    lifespan=lifespan
)

# --- リクエストモデル ---
class AnalyzeRequest(BaseModel):
    date: str = Field(..., description="対象日付 (YYYYMMDD形式, 例: '20260801')")
    turn_range: Optional[str] = Field(None, description="解析対象の手番範囲（未指定時はSGFの全手番を解析）")
    max_visits: int = Field(50, description="1局面あたりの探索手数（デフォルト: 50）")

# --- レスポンスモデル ---
class CandidateMove(BaseModel):
    move: str = Field(..., description="候補手（GTP座標表記、例: 'Q16'）")
    visits: int = Field(..., description="訪問探索回数")
    winrate: float = Field(..., description="勝率（％表記、例: 48.5）")
    scoreLead: float = Field(..., description="目数リード（黒基準または手番基準のリード目数）")
    pv: List[str] = Field(default_factory=list, description="読み筋（Principal Variation）")

class TurnAnalysis(BaseModel):
    turn: int = Field(..., description="手番番号（0: 初期局面）")
    player: str = Field(..., description="着手プレイヤー ('B' または 'W')")
    winrate: float = Field(..., description="最善手選択時の勝率（％）")
    scoreLead: float = Field(..., description="最善手選択時の目数リード")
    bestMove: str = Field(..., description="最善手")
    pv: List[str] = Field(default_factory=list, description="最善手からの読み筋")
    candidates: List[CandidateMove] = Field(default_factory=list, description="上位候補手の一覧")

class AnalyzeResponse(BaseModel):
    status: str = Field("success", description="ステータス")
    sgf_content: str = Field(..., description="解析対象のSGFファイルの内容（SGFテキスト全体）")
    total_moves: int = Field(..., description="SGFの総手数")
    analyzed_positions: int = Field(..., description="解析した局面数")
    results: List[TurnAnalysis] = Field(..., description="局面ごとの解析結果一覧")

def get_cache_file_path(req: AnalyzeRequest, cache_dir: str) -> str:
    """リクエストパラメータから一意のキャッシュファイルパスを生成"""
    turn_str = str(req.turn_range) if req.turn_range is not None else "all"
    raw_key = f"{req.date}_{turn_str}_{req.max_visits}"
    hash_key = hashlib.md5(raw_key.encode("utf-8")).hexdigest()
    filename = f"{req.date}_{hash_key}.json"
    return os.path.join(cache_dir, filename)

@app.get("/health")
def health_check():
    """ヘルスチェックエンドポイント"""
    return {
        "status": "healthy",
        "engine_running": analyzer.is_running()
    }

@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze_sgf_endpoint(req: AnalyzeRequest):
    """日付（YYYYMMDD）と手番範囲を受け取り、sgf_pickupフォルダ内の該当SGF棋譜をKataGoで解析して結果を返却します。"""
    project_root = os.path.dirname(os.path.abspath(__file__))
    cache_dir = os.path.join(project_root, "analysis_cache")
    os.makedirs(cache_dir, exist_ok=True)

    cache_path = get_cache_file_path(req, cache_dir)

    # 1. キャッシュが存在する場合はJSONから読み込んで返却
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
            print(f"[INFO] Returning cached analysis from: {cache_path}")
            return AnalyzeResponse(**cached_data)
        except Exception as e:
            print(f"[WARN] Failed to read cache ({cache_path}): {e}")

    # 2. キャッシュが存在しない場合は通常のSGF検索 & KataGo解析を実行
    pickup_dir = os.path.join(project_root, "sgf_pickup")
    
    # YYYYMMDD に前方一致する SGF ファイルを検索
    pattern = os.path.join(pickup_dir, f"{req.date}*.sgf")
    matched_files = glob.glob(pattern)

    # 見つからない場合、念のためアンダースコア等の区切りパターンも検索
    if not matched_files:
        pattern_under = os.path.join(pickup_dir, f"{req.date}_*.sgf")
        matched_files = glob.glob(pattern_under)

    if not matched_files:
        raise HTTPException(
            status_code=404,
            detail=f"日付 '{req.date}' に一致するSGFファイルが sgf_pickup フォルダに見つかりませんでした。"
        )

    source_file = matched_files[0]

    # SGFファイルの内容読み込み
    try:
        with open(source_file, "r", encoding="utf-8", errors="ignore") as f:
            sgf_content = f.read()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"SGFファイルの読み込みに失敗しました: {str(e)}"
        )

    # SGFパース
    try:
        parsed = parse_sgf(source_file)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"SGFのパースに失敗しました: {str(e)}"
        )

    total_moves = len(parsed["moves"])

    # turn_range のパースと検証
    if req.turn_range and req.turn_range.strip():
        try:
            turns = parse_turn_range(req.turn_range, max_available_turns=total_moves)
            valid_turns = [t for t in turns if 0 <= t <= total_moves]
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"`turn_range` の形式が不正です: {str(e)}"
            )
    else:
        # turn_rangeが指定されていない場合は0手目〜総手数の全手番
        valid_turns = list(range(0, total_moves + 1))

    if not valid_turns:
        raise HTTPException(
            status_code=400,
            detail=f"有効な手番が指定されていません（このSGFの有効手番は 0〜{total_moves} です）。"
        )

    # KataGoで解析実行
    try:
        raw_results = analyzer.analyze_sgf(
            source_file,
            max_visits=req.max_visits,
            analyze_turns=valid_turns
        )
        if not isinstance(raw_results, list):
            raw_results = [raw_results]
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"KataGo解析中にエラーが発生しました: {str(e)}"
        )

    # レスポンス整形
    summary_results: List[TurnAnalysis] = []
    for res in raw_results:
        turn = res.get("turnNumber", 0)
        root_info = res.get("rootInfo", {})
        player = root_info.get("currentPlayer", "?")
        winrate = round(root_info.get("winrate", 0.0) * 100, 2)
        score_lead = round(root_info.get("scoreLead", 0.0), 2)

        move_infos = res.get("moveInfos", [])
        candidates = []
        for m in move_infos:
            candidates.append(CandidateMove(
                move=m.get("move", "None"),
                visits=m.get("visits", 0),
                winrate=round(m.get("winrate", 0.0) * 100, 2),
                scoreLead=round(m.get("scoreLead", 0.0), 2),
                pv=m.get("pv", [])
            ))

        best_move = move_infos[0].get("move", "None") if move_infos else "None"
        best_pv = move_infos[0].get("pv", []) if move_infos else []

        summary_results.append(TurnAnalysis(
            turn=turn,
            player=player,
            winrate=winrate,
            scoreLead=score_lead,
            bestMove=best_move,
            pv=best_pv,
            candidates=candidates
        ))

    response_data = AnalyzeResponse(
        status="success",
        sgf_content=sgf_content,
        total_moves=total_moves,
        analyzed_positions=len(summary_results),
        results=summary_results
    )

    # 3. 解析結果をJSONファイルとして書き込み保存
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            if hasattr(response_data, "model_dump_json"):
                f.write(response_data.model_dump_json(indent=2))
            else:
                f.write(response_data.json(indent=2))
        print(f"[INFO] Saved analysis cache to: {cache_path}")
    except Exception as e:
        print(f"[WARN] Failed to write cache ({cache_path}): {e}")

    return response_data

if __name__ == "__main__":
    # ポート8081以外のポート（8000）で起動
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
