import os
import requests
import time
import json
import re
from urllib.parse import parse_qs
from dotenv import load_dotenv
from requests_oauthlib import OAuth1
from plurk_oauth import PlurkAPI
from datetime import datetime


# ==========================================
# 深度開發：Keys讀取邏輯 (支援靜態寫入與本地開發)
# ==========================================
def get_keys():
    try:
        # 優先嘗試讀取由 GitHub Actions 於編譯時動態產生的模組
        import config_keys
        ck = config_keys.CONSUMER_KEY
        cs = config_keys.CONSUMER_SECRET
    except ImportError:
        # 若模組不存在（如本地開發環境），則讀取 tool.env
        load_dotenv("tool.env")
        ck = os.getenv("PLURK_CONSUMER_KEY")
        cs = os.getenv("PLURK_CONSUMER_SECRET")
    
    # 讀取 User 個人的 Access Token (通常儲存在本地環境)
    at = os.getenv("PLURK_ACCESS_TOKEN")
    as_ = os.getenv("PLURK_ACCESS_TOKEN_SECRET")
    
    return ck, cs, at, as_

# 環境設定
BACKUP_DIR = "backup_js"

# 噗浪 OAuth 端點
REQUEST_TOKEN_URL = "https://www.plurk.com/OAuth/request_token"
AUTHORIZE_URL = "https://www.plurk.com/OAuth/authorize"
ACCESS_TOKEN_URL = "https://www.plurk.com/OAuth/access_token"

# ... [base36_encode, get_last_saved_id, get_new_tokens, update_manifest 函式保持不變] ...

def base36_encode(number):
    """將噗文 ID 轉換為 36 進位以產生 URL"""
    chars = '0123456789abcdefghijklmnopqrstuvwxyz'
    if number == 0: return '0'
    res = ''
    while number:
        number, i = divmod(number, 36)
        res = chars[i] + res
    return res

def get_last_saved_id():
    """掃描現有備份檔案，找出已存的最大 plurk_id"""
    if not os.path.exists(BACKUP_DIR):
        return 0
    
    last_id = 0
    for filename in os.listdir(BACKUP_DIR):
        if filename.endswith(".js") and filename != "manifest.js":
            with open(os.path.join(BACKUP_DIR, filename), "r", encoding="utf-8") as f:
                content = f.read()
                # 使用正則表達式快速搜尋 plurk_id
                ids = re.findall(r'"plurk_id":\s*(\d+)', content)
                if ids:
                    last_id = max(last_id, max(map(int, ids)))
    return last_id

def get_new_tokens(ck, cs):
    oauth = OAuth1(ck, client_secret=cs)
    r = requests.post(REQUEST_TOKEN_URL, auth=oauth)
    creds = parse_qs(r.text)
    req_token = creds.get('oauth_token')[0]
    req_secret = creds.get('oauth_token_secret')[0]
    print(f"\n請開啟網頁進行授權：\n{AUTHORIZE_URL}?oauth_token={req_token}")
    verifier = input("\n請輸入驗證碼: ").strip()
    oauth = OAuth1(ck, client_secret=cs, resource_owner_key=req_token, 
                   resource_owner_secret=req_secret, verifier=verifier)
    r = requests.post(ACCESS_TOKEN_URL, auth=oauth)
    final_creds = parse_qs(r.text)
    return final_creds.get('oauth_token')[0], final_creds.get('oauth_token_secret')[0]

def update_manifest(backup_dir):
    """更新月份清單索引"""
    months = [f[:-3] for f in os.listdir(backup_dir) if f.endswith(".js") and f != "manifest.js"]
    months.sort(reverse=True)
    json_content = json.dumps(months)
    manifest_path = os.path.join(backup_dir, 'manifest.js')
    with open(manifest_path, 'w', encoding='utf-8') as f:
        f.write(f'if (!window.BackupData) window.BackupData = {{ plurks: {{}} }};\n')
        f.write(f'BackupData.months = {json_content};')
    print(f"✅ 已更新索引：{months}")

def main():
    # 使用最佳化後的Keys讀取函式
    ck, cs, at, as_ = get_keys()

    if not ck or not cs:
        print("❌ 錯誤：找不到 Consumer Key 或 Secret。請檢查環境設定。")
        return

    if not at or not as_:
        at, as_ = get_new_tokens(ck, cs)
        # 授權成功後，建議提示 User 手動存入 tool.env (針對開發者)
        # 或是你可以考慮自動幫 User 寫入檔案（對一般 User 較友善）

    plurk = PlurkAPI(ck, cs)
    plurk.authorize(at, as_)

    # ... [其餘邏輯保持不變] ...

    # 確保備份目錄存在
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)

    last_saved_id = get_last_saved_id()
    if last_saved_id > 0:
        print(f"🔍 偵測到現有備份，將從 ID {last_saved_id} 之後抓取新內容。")

    offset = None
    monthly_data = {}
    total_new = 0
    stop_backup = False

    print("\n--- 開始抓取最愛噗文 ---")

    while not stop_backup:
        params = {'filter': 'favorite', 'limit': 30}
        if offset:
            params['offset'] = offset

        res = plurk.callAPI('/APP/Timeline/getPlurks', params)

        if res and 'plurks' in res and len(res['plurks']) > 0:
            plurks = res['plurks']
            for p in plurks:
                # 增量更新檢查
                if p['plurk_id'] <= last_saved_id:
                    print(f"🏁 已追上現有紀錄 (ID: {p['plurk_id']})，停止抓取。")
                    stop_backup = True
                    break

                # 處理日期與分組
                dt = datetime.strptime(p['posted'], "%a, %d %b %Y %H:%M:%S GMT")
                ym = dt.strftime("%Y_%m")
                if ym not in monthly_data:
                    monthly_data[ym] = []
                
                # 加入 URL
                p['plurk_url'] = f"https://www.plurk.com/p/{base36_encode(p['plurk_id'])}"
                monthly_data[ym].append(p)
                total_new += 1
            
            if stop_backup: break
            offset = plurks[-1]['posted']
            print(f"已抓取 {total_new} 則新噗文...")
            time.sleep(1)
        else:
            break

    if total_new == 0:
        print("🙌 沒有新噗文需要備份。")
        return

    # 儲存新資料 (採覆蓋或合併方式)
    for ym, data in monthly_data.items():
        file_path = os.path.join(BACKUP_DIR, f"{ym}.js")
        
        # 若該月份已存在，則讀取舊資料合併
        existing_data = []
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                # 簡單抓取 JSON 部分 (這裡假設結構一致)
                try:
                    json_str = content.split(f'BackupData.plurks["{ym}"] = ')[1].rstrip(';')
                    existing_data = json.loads(json_str)
                except:
                    existing_data = []

        # 合併新舊資料並依時間排序
        combined = data + existing_data
        combined.sort(key=lambda x: x['plurk_id'], reverse=True)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f'if (!window.BackupData) window.BackupData = {{ plurks: {{}} }};\n')
            f.write(f'BackupData.plurks["{ym}"] = {json.dumps(combined, ensure_ascii=False)};')

    update_manifest(BACKUP_DIR)
    print(f"\n🎉 備份完成！共新增 {total_new} 則噗文。")

if __name__ == "__main__":
    main()