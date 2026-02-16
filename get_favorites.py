# Copyright (c) 2026 rkwithb (https://github.com/rkwithb)
# Licensed under CC BY-NC 4.0 (Non-Commercial Use Only)
# Disclaimer: Use at your own risk. The author is not responsible for any damages.

import io
import json
import os
import re
import sys
import time
import sqlite3
from datetime import datetime
from urllib.parse import parse_qs
from dotenv import load_dotenv
import requests
from requests_oauthlib import OAuth1
from plurk_oauth import PlurkAPI

# for debugging
import traceback

# ==========================================
# 初始化與路徑設定 (加入 BASE_DIR 保護)
# ==========================================
# 確保在 CLI/EXE 環境下都能精準定位執行檔所在目錄
BASE_DIR = os.path.dirname(os.path.abspath(sys.argv[0] if getattr(sys.modules['__main__'], '__file__', None) else sys.executable))

BACKUP_DIR = os.path.join(BASE_DIR, "backup_js")
DB_PATH = os.path.join(BACKUP_DIR, "plurk_favorites.db")
TRACK_FILE = os.path.join(BACKUP_DIR, "affected_months.txt")
INDEX_PATH = os.path.join(BASE_DIR, "index.html")
STYLE_PATH = os.path.join(BASE_DIR, "style.css")

if not os.path.exists(BACKUP_DIR):
    os.makedirs(BACKUP_DIR)

def safe_input(prompt, default="n"):
    try:
        if not sys.stdin or not sys.stdin.isatty(): return default
        return input(prompt).lower()
    except (EOFError, OSError): return default

def safe_print(*args, **kwargs):
    """強化版安全輸出，應對 Wine/CI 環境下的 I/O 關閉問題"""
    try:
        if sys.stdout and not sys.stdout.closed:
            print(*args, **kwargs)
    except (ValueError, OSError) as e:
        # 如果是 stdout 關閉，在 CI 環境嘗試輸出到 stderr，一般環境則優雅忽略
        if "closed file" in str(e):
            if os.getenv('GITHUB_ACTIONS') == 'true':
                try:
                    sys.__stderr__.write(f"\n[DEBUG] Detected closed stdout: {args}\n")
                except: pass
        else:
            # 非 I/O 關閉錯誤則視情況拋出
            if os.getenv('GITHUB_ACTIONS') != 'true': raise

# ==========================================
# 資料庫操作邏輯
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS favorites (
            plurk_id INTEGER PRIMARY KEY,
            posted TEXT,
            raw_json TEXT
        )
    ''')
    conn.commit()
    return conn

def save_to_db(conn, p):
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO favorites (plurk_id, posted, raw_json)
        VALUES (?, ?, ?)
    ''', (p['plurk_id'], p['posted'], json.dumps(p, ensure_ascii=False)))
    conn.commit()

# ==========================================
# 金鑰與 Token 管理
# ==========================================
def get_keys():
    env_file = os.path.join(BASE_DIR, "tool.env")
    if not os.path.exists(env_file):
        safe_print(f"❌ 找不到 {env_file}")
        return None, None, None, None
    load_dotenv(env_file)
    return os.getenv("PLURK_CONSUMER_KEY"), os.getenv("PLURK_CONSUMER_SECRET"), \
           os.getenv("PLURK_ACCESS_TOKEN"), os.getenv("PLURK_ACCESS_TOKEN_SECRET")

def get_last_saved_id(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(plurk_id) FROM favorites")
    res = cursor.fetchone()[0]
    return res if res else 0

def base36_encode(number):
    chars = '0123456789abcdefghijklmnopqrstuvwxyz'
    if number == 0: return '0'
    res = ''
    while number:
        number, i = divmod(number, 36)
        res = chars[i] + res
    return res

# ==========================================
# 備份模式選擇
# ==========================================
def select_backup_mode(last_saved_id):
    safe_print("\n請選擇備份模式：")
    safe_print("1. 指定日期重抓 (檢查從指定日期到今天的所有最愛)")
    safe_print(f"2. 增量備份模式 (檢查 ID: {last_saved_id} 之後的新噗)")
    safe_print("3. 完整備份模式 (重新備份所有歷史紀錄 JS)")

    choice = safe_input("請輸入選項 [1/2/3] (預設 2): ", "2").strip()

    if choice == "1":
        date_str = safe_input("請輸入開始日期 (YYYYMMDD 例: 20251201): ").strip()
        try:
            return 'date', datetime.strptime(date_str, "%Y%m%d")
        except ValueError:
            safe_print("❌ 日期格式錯誤，切換回增量模式。")
            return 'id', last_saved_id
    elif choice == "3":
        return 'full', 0
    return 'id', last_saved_id

# ==========================================
# JS 產出邏輯
# ==========================================
def export_js_files(conn, mode_type):
    cursor = conn.cursor()
    months_to_update = set()

    if mode_type == 'full':
        cursor.execute("SELECT DISTINCT strftime('%Y_%m', datetime(posted, 'weekday 0', '-7 days')) as ym FROM favorites")
        cursor.execute("SELECT posted FROM favorites")
        for row in cursor.fetchall():
            dt = datetime.strptime(row[0], "%a, %d %b %Y %H:%M:%S GMT")
            months_to_update.add(dt.strftime("%Y_%m"))
    else:
        if os.path.exists(TRACK_FILE):
            with open(TRACK_FILE, "r", encoding="utf-8") as f:
                months_to_update = {line.strip() for line in f if line.strip()}

    if not months_to_update:
        safe_print("🙌 無需更新 JS 檔案。")
        return

    safe_print(f"💾 正在產出 JS 檔案: {sorted(list(months_to_update))}")
    for ym in months_to_update:
        # 這裡從資料庫篩選該月份資料 (使用 LIKE 比對 posted 內容)
        # 注意：API 的日期格式為 "Fri, 05 Jun 2009..."，需精準轉換或比對

        cursor.execute("SELECT raw_json FROM favorites ORDER BY plurk_id DESC")
        all_data = [json.loads(row[0]) for row in cursor.fetchall()]

        monthly_plurks = []
        for p in all_data:
            p_dt = datetime.strptime(p['posted'], "%a, %d %b %Y %H:%M:%S GMT")
            if p_dt.strftime("%Y_%m") == ym:
                p['plurk_url'] = f"https://www.plurk.com/p/{base36_encode(p['plurk_id'])}"
                monthly_plurks.append(p)

        if monthly_plurks:
            file_path = os.path.join(BACKUP_DIR, f"{ym}.js")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write('if (!window.BackupData) window.BackupData = { plurks: {} };\n')
                f.write(f'BackupData.plurks["{ym}"] = {json.dumps(monthly_plurks, ensure_ascii=False)};')

    all_js = sorted([f[:-3] for f in os.listdir(BACKUP_DIR) if f.endswith(".js") and f != "manifest.js"], reverse=True)
    with open(os.path.join(BACKUP_DIR, 'manifest.js'), 'w', encoding='utf-8') as f:
        f.write('if (!window.BackupData) window.BackupData = { plurks: {} };\n')
        f.write(f'BackupData.months = {json.dumps(all_js)};')

# ==========================================
# 核心備份任務
# ==========================================
def run_backup_task(plurk, conn, mode_type, criteria_value):
    # 模式 1 & 2 開頭先刪除追蹤檔
    if mode_type in ['id', 'date'] and os.path.exists(TRACK_FILE):
        os.remove(TRACK_FILE)

    affected_months = set()
    offset = None
    stop_backup = False
    total_new = 0

    # 若是 full 模式，其實可以設定 criteria_value = 0 走 id 模式邏輯
    safe_print("\n--- 開始抓取最愛噗文 ---")
    actual_mode = 'id' if mode_type == 'full' else mode_type

    while not stop_backup:
        params = {'filter': 'favorite', 'limit': 30}
        if offset: params['offset'] = offset

        try:
            res = plurk.callAPI('/APP/Timeline/getPlurks', params)
        except Exception as e:
            safe_print(f"❌ API 呼叫失敗: {e}")
            break

        if not res or not res.get('plurks'): break

        for p in res['plurks']:
            p_date = datetime.strptime(p['posted'], "%a, %d %b %Y %H:%M:%S GMT")

            # 停止條件檢查
            if actual_mode == 'id' and p['plurk_id'] <= criteria_value:
                stop_backup = True; break
            if actual_mode == 'date' and p_date < criteria_value:
                stop_backup = True; break

            # 存入資料庫
            save_to_db(conn, p)
            affected_months.add(p_date.strftime("%Y_%m"))
            total_new += 1

        if stop_backup: break
        offset = datetime.strptime(res['plurks'][-1]['posted'], "%a, %d %b %Y %H:%M:%S GMT").isoformat()
        safe_print(f"已讀取 {total_new} 則...")
        time.sleep(1)

    # 紀錄受影響月份
    if mode_type != 'full' and affected_months:
        with open(TRACK_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(sorted(list(affected_months))))

    export_js_files(conn, mode_type)
    safe_print(f"\n🎉 任務完成！本次新增/檢查了 {total_new} 則噗文。")

def setup_env():
    """建立 .env 範本並引導使用者操作"""
    env_file = os.path.join(BASE_DIR, "tool.env")
    with open(env_file, "w", encoding="utf-8") as f:
        f.write("PLURK_CONSUMER_KEY=\n")
        f.write("PLURK_CONSUMER_SECRET=\n")
        f.write("PLURK_ACCESS_TOKEN=\n")
        f.write("PLURK_ACCESS_TOKEN_SECRET=\n")

    safe_print(f"❌ 找不到 tool.env，已在 {BASE_DIR} 為您建立範本。")
    safe_print("--------------------------------------------------")
    safe_print("引導流程：")
    safe_print("1. 請至 https://www.plurk.com/PlurkApp/ 申請 App。")
    safe_print("2. 申請教學請見 https://github.com/rkwithb/Plurk-Get-Favorites-Tool/blob/main/Tutorial/plurkappkey.md")
    safe_print("3. 將四個key填入 tool.env 檔案中並儲存。")
    safe_print("4. 重新執行此程式。")
    safe_print("--------------------------------------------------")
    return

def main():
    # 弱化編碼重導向：僅在必要且安全時執行
    if sys.platform == "win32" and hasattr(sys.stdout, 'buffer') and not sys.stdout.closed:
        try:
            # 檢查目前是否已經是 utf-8，避免重複封裝
            if getattr(sys.stdout, 'encoding', '').lower() != 'utf-8':
                sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)
        except Exception: pass

    env_file = os.path.join(BASE_DIR, "tool.env")
    if not os.path.exists(env_file):
        return setup_env()

    ck, cs, at, as_ = get_keys()
    if not ck or not cs or not at or not as_:
        safe_print("❌ tool.env 金鑰填寫不完整。")
        return

    safe_print("==================================================")
    safe_print("🚀 Plurk Favorites Backup Tool v2.0.1 (SQLite Edition)")
    safe_print(f"📅 執行時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    safe_print(f"📂 根目錄: {BASE_DIR}")
    safe_print("==================================================")

    conn = init_db()
    try:
        plurk = PlurkAPI(ck, cs)
        plurk.authorize(at, as_)

        last_id = get_last_saved_id(conn)
        if last_id == 0:
            safe_print("💡 偵測到尚未有備份紀錄，將自動執行【模式 3：完整備份】...")
            mode_type, criteria = 'full', 0
        else:
            safe_print(f"🔍 上次備份最後 ID: {last_id}")
            mode_type, criteria = select_backup_mode(last_id)

        run_backup_task(plurk, conn, mode_type, criteria)
    finally:
        conn.close()

if __name__ == "__main__":
    main()