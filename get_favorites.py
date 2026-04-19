# Copyright 2026 rkwithb
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


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

# ==========================================
# 初始化與路徑設定
# ==========================================
BACKUP_DIR = "backup_js"
DB_PATH = os.path.join(BACKUP_DIR, "plurk_favorites.db")
TRACK_FILE = os.path.join(BACKUP_DIR, "affected_months.txt")
# 環境設定
REQUEST_TOKEN_URL = "https://www.plurk.com/OAuth/request_token"
AUTHORIZE_URL = "https://www.plurk.com/OAuth/authorize"
ACCESS_TOKEN_URL = "https://www.plurk.com/OAuth/access_token"


if not os.path.exists(BACKUP_DIR):
    os.makedirs(BACKUP_DIR)

# (I/O 強健性初始化代碼略，與原版相同...)
if sys.platform == "win32":
    if sys.stdout is not None and hasattr(sys.stdout, 'buffer'):
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)
        except Exception: pass

def safe_input(prompt, default="n"):
    try:
        if not sys.stdin or not sys.stdin.isatty(): return default
        return input(prompt).lower()
    except (EOFError, OSError): return default

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



def setup_env():
    """建立 .env 範本並引導使用者操作"""
    with open("tool.env", "w", encoding="utf-8") as f:
        f.write("PLURK_CONSUMER_KEY=\n")
        f.write("PLURK_CONSUMER_SECRET=\n")
        f.write("PLURK_ACCESS_TOKEN=\n")
        f.write("PLURK_ACCESS_TOKEN_SECRET=\n")

    print("[!!] 找不到 tool.env，已為您建立範本。")
    print("--------------------------------------------------")
    print("引導流程：")
    print("1. 請至 https://www.plurk.com/PlurkApp/ 申請 App。")
    print("2. 申請教學請見https://github.com/rkwithb/Plurk-Get-Favorites-Tool/blob/main/Tutorial/plurkappkey.md")
    print("3. 將四個key填入 tool.env 檔案中並儲存。")
    print("4. 重新執行此程式。")
    print("--------------------------------------------------")
    return # 結束函數


def get_new_tokens(ck, cs):
    oauth = OAuth1(ck, client_secret=cs)
    r = requests.post(REQUEST_TOKEN_URL, auth=oauth)
    creds = parse_qs(r.text)
    req_token = creds.get('oauth_token')[0]
    req_secret = creds.get('oauth_token_secret')[0]
    print(f"\n請開啟網頁進行授權：\n{AUTHORIZE_URL}?oauth_token={req_token}")
    verifier = safe_input("\n請輸入驗證碼: ").strip()
    oauth = OAuth1(ck, client_secret=cs, resource_owner_key=req_token,
                   resource_owner_secret=req_secret, verifier=verifier)
    r = requests.post(ACCESS_TOKEN_URL, auth=oauth)
    final_creds = parse_qs(r.text)
    return final_creds.get('oauth_token')[0], final_creds.get('oauth_token_secret')[0]

def get_keys():
    env_file = "tool.env"
    if not os.path.exists(env_file):
        print(f"[!!] 找不到 {env_file}")
        return None, None, None, None
    load_dotenv(env_file)
    return os.getenv("PLURK_CONSUMER_KEY"), os.getenv("PLURK_CONSUMER_SECRET"), \
           os.getenv("PLURK_ACCESS_TOKEN"), os.getenv("PLURK_ACCESS_TOKEN_SECRET")

def save_keys(ck, cs, at, as_):
    with open("tool.env", "w", encoding="utf-8") as f:
        f.write(f"PLURK_CONSUMER_KEY={ck}\n")
        f.write(f"PLURK_CONSUMER_SECRET={cs}\n")
        f.write(f"PLURK_ACCESS_TOKEN={at}\n")
        f.write(f"PLURK_ACCESS_TOKEN_SECRET={as_}\n")
    print("[OK] 已將金鑰與 Access Token 儲存至 tool.env")

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
    print("\n請選擇備份模式：")
    print("1. 指定日期重抓 (檢查從指定日期到今天的所有最愛)")
    print(f"2. 增量備份模式 (檢查 ID: {last_saved_id} 之後的新噗)")
    print("3. 完整備份模式 (重新產出所有歷史紀錄 JS)")

    choice = safe_input("請輸入選項 [1/2/3] (預設 2): ", "2").strip()

    if choice == "1":
        date_str = input("請輸入開始日期 (YYYYMMDD): ").strip()
        return 'date', datetime.strptime(date_str, "%Y%m%d")
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
        cursor.execute("SELECT DISTINCT strftime('%Y_%m', datetime(posted, 'weekday 0', '-7 days')) as ym FROM favorites") # 簡化逻辑：直接從資料獲取所有月份
        cursor.execute("SELECT posted FROM favorites")
        for row in cursor.fetchall():
            dt = datetime.strptime(row[0], "%a, %d %b %Y %H:%M:%S GMT")
            months_to_update.add(dt.strftime("%Y_%m"))
    else:
        if os.path.exists(TRACK_FILE):
            with open(TRACK_FILE, "r", encoding="utf-8") as f:
                months_to_update = {line.strip() for line in f if line.strip()}

    if not months_to_update:
        print("[OK] 無需更新 JS 檔案。")
        return

    print(f"[>>] 正在產出 JS 檔案: {sorted(list(months_to_update))}")
    for ym in months_to_update:
        # 這裡從資料庫篩選該月份資料 (使用 LIKE 比對 posted 內容)
        # 注意：API 的日期格式為 "Fri, 05 Jun 2009..."，需精準轉換或比對
        cursor.execute("SELECT raw_json FROM favorites ORDER BY plurk_id DESC")
        all_data = [json.loads(row[0]) for row in cursor.fetchall()]

        # 篩選屬於該月份的噗文
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

    # 更新 manifest
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

    print("\n--- 開始抓取最愛噗文 ---")

    # 若是 full 模式，其實可以設定 criteria_value = 0 走 id 模式邏輯
    actual_mode = 'id' if mode_type == 'full' else mode_type

    while not stop_backup:
        params = {'filter': 'favorite', 'limit': 30}
        if offset: params['offset'] = offset

        res = plurk.callAPI('/APP/Timeline/getPlurks', params)
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
        print(f"已讀取 {total_new} 則...")
        time.sleep(1)

    # 紀錄受影響月份
    if mode_type != 'full' and affected_months:
        with open(TRACK_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(sorted(list(affected_months))))

    # 執行 JS 產出同步
    export_js_files(conn, mode_type)
    print(f"\n[OK] 任務完成！本次新增/檢查了 {total_new} 則噗文。")



def main():

    # ---「引導流程」的新位置 ---
    if not os.path.exists("tool.env"):
        return setup_env()  # 執行引導並直接結束 main
    # --- 檢查keys ---
    print("-----檢查金鑰-----")
    ck, cs, at, as_ = get_keys()
    if not ck or not cs:
        print("[!!] PLURK_CONSUMER_KEY / PLURK_CONSUMER_SECRET 尚未填寫，請編輯 tool.env。")
        return

    if not at or not as_:
        at, as_ = get_new_tokens(ck, cs)
        save_keys(ck, cs, at, as_)

    print("-----金鑰設定完整-----")
    # (setup_env 檢查後)
    print("==================================================")
    print("[GO] Plurk Favorites Backup Tool v2.0 (SQLite Edition)")
    print(f"[time] 執行時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("==================================================")
    conn = init_db()
    plurk = PlurkAPI(ck, cs)
    plurk.authorize(at, as_)

    last_id = get_last_saved_id(conn)
    if last_id == 0:
        print("[**] 偵測到尚未有備份紀錄，將自動執行【模式 3：完整備份】...")
        mode_type, criteria = 'full', 0
    else:
        # 正常選擇模式
        print(f"[..] 上次備份最後 ID: {last_id}")
        mode_type, criteria = select_backup_mode(last_id)

    # 4. 執行任務
    run_backup_task(plurk, conn, mode_type, criteria)
    conn.close()

if __name__ == "__main__":
    main()