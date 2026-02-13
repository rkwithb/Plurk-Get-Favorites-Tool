
# Copyright (c) 2026 rkwithb (https://github.com/rkwithb)
# Licensed under CC BY-NC 4.0 (Non-Commercial Use Only)
# Disclaimer: Use at your own risk. The author is not responsible for any damages.

# 1. (Standard library imports)
import io
import json
import os
import re
import sys
import time
from datetime import datetime
from urllib.parse import parse_qs

# 2. (Related third party imports)
from dotenv import load_dotenv
import requests
from requests_oauthlib import OAuth1

# 3. (Local application/library specific imports)
from plurk_oauth import PlurkAPI

# ==========================================
# I/O 強健性初始化
# ==========================================
if sys.platform == "win32":
    if sys.stdout is not None and hasattr(sys.stdout, 'buffer'):
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)
        except Exception:
            pass
    elif sys.stdout is None:
        sys.stdout = open(os.devnull, 'w')

def safe_input(prompt, default="n"):
    try:
        if not sys.stdin or not sys.stdin.isatty():
            return default
        return input(prompt).lower()
    except (EOFError, OSError):
        return default

# ==========================================
# Keys 管理邏輯
# ==========================================
def save_keys(ck, cs, at, as_):
    with open("tool.env", "w", encoding="utf-8") as f:
        f.write(f"PLURK_CONSUMER_KEY={ck}\n")
        f.write(f"PLURK_CONSUMER_SECRET={cs}\n")
        f.write(f"PLURK_ACCESS_TOKEN={at}\n")
        f.write(f"PLURK_ACCESS_TOKEN_SECRET={as_}\n")
    print("✅ 已將金鑰與 Access Token 儲存至 tool.env")

def get_keys():
    env_file = "tool.env"
    if not os.path.exists(env_file):
        with open(env_file, "w", encoding="utf-8") as f:
            f.write("PLURK_CONSUMER_KEY=\n")
            f.write("PLURK_CONSUMER_SECRET=\n")
            f.write("PLURK_ACCESS_TOKEN=\n")
            f.write("PLURK_ACCESS_TOKEN_SECRET=\n")
        print(f"❌ 找不到 {env_file}，已為您建立範本。")
        print("請至 https://www.plurk.com/PlurkApp/ 申請並填入 Consumer Key/Secret。")
        return None, None, None, None

    load_dotenv(env_file)
    ck = os.getenv("PLURK_CONSUMER_KEY")
    cs = os.getenv("PLURK_CONSUMER_SECRET")
    at = os.getenv("PLURK_ACCESS_TOKEN")
    as_ = os.getenv("PLURK_ACCESS_TOKEN_SECRET")
    return ck, cs, at, as_

# 環境設定
BACKUP_DIR = "backup_js"
REQUEST_TOKEN_URL = "https://www.plurk.com/OAuth/request_token"
AUTHORIZE_URL = "https://www.plurk.com/OAuth/authorize"
ACCESS_TOKEN_URL = "https://www.plurk.com/OAuth/access_token"

def base36_encode(number):
    chars = '0123456789abcdefghijklmnopqrstuvwxyz'
    if number == 0: return '0'
    res = ''
    while number:
        number, i = divmod(number, 36)
        res = chars[i] + res
    return res

def get_last_saved_id():
    if not os.path.exists(BACKUP_DIR):
        return 0

    last_id = 0
    files = [f for f in os.listdir(BACKUP_DIR) if f.endswith(".js") and f != "manifest.js"]

    if not files:
        return 0

    for filename in files:
        with open(os.path.join(BACKUP_DIR, filename), "r", encoding="utf-8") as f:
            content = f.read()
            ids = re.findall(r'"plurk_id":\s*(\d+)', content)
            if ids:
                last_id = max(last_id, max(map(int, ids)))

    # 只有在真的掃描完所有檔案都沒 ID 時才會是 0
    return last_id

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

def update_manifest(backup_dir):
    months = [f[:-3] for f in os.listdir(backup_dir) if f.endswith(".js") and f != "manifest.js"]
    months.sort(reverse=True)
    json_content = json.dumps(months)
    manifest_path = os.path.join(backup_dir, 'manifest.js')
    with open(manifest_path, 'w', encoding='utf-8') as f:
        f.write(f'if (!window.BackupData) window.BackupData = {{ plurks: {{}} }};\n')
        f.write(f'BackupData.months = {json_content};')
    print(f"✅ 已更新索引：{months}")

# ==========================================
# (1) & (2) 新增功能：選擇模式邏輯
# ==========================================

def select_backup_mode(last_saved_id):
    print("\n請選擇備份模式：")
    print(f"1. 指定日期重抓 (檢查從指定日期到今天的所有最愛)")

    if last_saved_id > 0:
        print(f"2. 增量備份模式 (僅檢查上次備份 ID: {last_saved_id} 之後的新噗)")
        print(f"3. 完整備份模式 (強制重新抓取所有歷史紀錄)")
        default_choice = "2"
    else:
        # 當 last_saved_id == 0，代表這是第一次備份或備份檔不存在
        print(f"2. 完整備份模式 (未偵測到現有備份，將抓取所有紀錄)")
        default_choice = "2"

    choice = safe_input(f"請輸入選項 [1/2/3] (預設 {default_choice}): ", default_choice).strip()

    if choice == "1":
        while True:
            date_str = input("請輸入開始日期 (格式 YYYYMMDD，例如 20251201): ").strip()
            try:
                target_date = datetime.strptime(date_str, "%Y%m%d")
                return 'date', target_date
            except ValueError:
                print("❌ 格式錯誤，請重新輸入。")

    elif choice == "3":
        # 使用者明確要求完整備份，強制將 ID 設為 0
        print("🚀 執行【完整備份】，將掃描所有歷史紀錄...")
        return 'id', 0

    elif choice == "2":
        if last_saved_id == 0:
            print("🚀 未發現舊紀錄，執行【完整備份】...")
            return 'id', 0
        else:
            print(f"🚀 執行【增量備份】，自 ID: {last_saved_id} 起...")
            return 'id', last_saved_id

    # 預防性處理：若輸入錯誤選項，且有舊 ID 則走增量，無則走完整
    return ('id', last_saved_id) if last_saved_id > 0 else ('id', 0)

# ==========================================
# (3) 新增功能：獨立的備份執行邏輯
# ==========================================
def run_backup_task(plurk, mode_type, criteria_value):
    """
    執行備份的主要迴圈與儲存邏輯
    """
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)

    offset = None
    monthly_data = {}
    total_processed = 0
    stop_backup = False

    print("\n--- 開始抓取最愛噗文 ---")

    while not stop_backup:
        # 準備 API 參數
        params = {'filter': 'favorite', 'limit': 30}
        if offset:
            params['offset'] = offset

        # 呼叫 API
        res = plurk.callAPI('/APP/Timeline/getPlurks', params)

        if res and 'plurks' in res and len(res['plurks']) > 0:
            plurks = res['plurks']
            for p in plurks:
                # 1. 處理時間戳記 (解析 API 回傳的 GMT 格式)
                p_date = datetime.strptime(p['posted'], "%a, %d %b %Y %H:%M:%S GMT")

                # 2. 檢查停止條件
                if mode_type == 'id':
                    if p['plurk_id'] <= criteria_value:
                        print(f"🏁 已追上現有紀錄 (ID: {p['plurk_id']})，停止抓取。")
                        stop_backup = True
                        break
                elif mode_type == 'date':
                    if p_date < criteria_value:
                        print(f"🏁 已到達指定日期邊界 ({p_date.strftime('%Y-%m-%d')})，停止抓取。")
                        stop_backup = True
                        break

                # 3. 整理資料
                ym = p_date.strftime("%Y_%m")
                if ym not in monthly_data:
                    monthly_data[ym] = []

                p['plurk_url'] = f"https://www.plurk.com/p/{base36_encode(p['plurk_id'])}"
                monthly_data[ym].append(p)
                total_processed += 1

            if stop_backup: break

            # 4. 更新 offset (關鍵修正：轉換為 ISO 格式)
            # 取最後一則噗文的時間作為下一頁的起點
            last_posted_str = plurks[-1]['posted']
            last_dt = datetime.strptime(last_posted_str, "%a, %d %b %Y %H:%M:%S GMT")
            offset = last_dt.isoformat()

            print(f"目前已讀取 {total_processed} 則噗文 (下一頁起點: {offset})...")
            time.sleep(1)
        else:
            # 若 res 為空或格式不對則停止
            break

    # --- 儲存與去重複邏輯 ---
    if total_processed == 0:
        print("🙌 沒有需更新的噗文。")
        return

    print("\n💾 正在寫入檔案並處理重複項...")
    for ym, new_plurks_list in monthly_data.items():
        file_path = os.path.join(BACKUP_DIR, f"{ym}.js")
        existing_data = []

        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                try:
                    json_str = content.split(f'BackupData.plurks["{ym}"] = ')[1].rstrip(';')
                    existing_data = json.loads(json_str)
                except Exception:
                    existing_data = []

        # 合併並以 ID 去重
        plurk_map = {p['plurk_id']: p for p in existing_data}
        for p in new_plurks_list:
            plurk_map[p['plurk_id']] = p

        combined = sorted(plurk_map.values(), key=lambda x: x['plurk_id'], reverse=True)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f'if (!window.BackupData) window.BackupData = {{ plurks: {{}} }};\n')
            f.write(f'BackupData.plurks["{ym}"] = {json.dumps(combined, ensure_ascii=False)};')

    update_manifest(BACKUP_DIR)
    print(f"\n🎉 處理完成！共處理 {total_processed} 則噗文。")

def main():
    ck, cs, at, as_ = get_keys()

    if not ck or not cs:
        return

    if not at or not as_:
        at, as_ = get_new_tokens(ck, cs)
        save_keys(ck, cs, at, as_)

    # 初始化 API
    plurk = PlurkAPI(ck, cs)
    plurk.authorize(at, as_)

    # 取得上次備份 ID
    last_saved_id = get_last_saved_id()

    # (1) & (2) 呼叫選擇模式函式
    mode_type, criteria_value = select_backup_mode(last_saved_id)

    # (3) 呼叫備份執行函式
    run_backup_task(plurk, mode_type, criteria_value)

if __name__ == "__main__":
    main()