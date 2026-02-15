# Web Assets for Plurk Favorites Tool
# 這裡存放靜態網頁資源，使用標準字串以保留 JavaScript 的 ${} 語法

INDEX_HTML_CONTENT = """<!-- ⚠️ IMPORTANT: Remember to update web_assets.py after editing this file. / 修改後請記得同步更新 web_assets.py。  -->
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <title>Plurk Archive Browser</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>

    <header>
        <h1>Archive</h1>
        <div class="subtitle">Collected Favorite Plurks</div>
    </header>

    <div class="nav-container">
        <div class="nav-item">
            <label>Month</label>
            <select id="month-select"><option value="">Select Date</option></select>
        </div>
        <div class="nav-item">
            <label>Filter</label>
            <select id="type-filter">
                <option value="all">All</option>
                <option value="0">Public</option>
                <option value="1">Private</option>
                <option value="4">Anonymous</option>
            </select>
        </div>
        <div class="nav-item">
            <label>Search</label>
            <input type="text" id="search-input" placeholder="Keyword...">
        </div>
        <div class="nav-item">
            <input type="file" id="bg-upload" accept="image/*" style="display:none;" onchange="handleBgUpload(this)">
            <span class="bg-btn" onclick="document.getElementById('bg-upload').click()">Choose BG</span>
            <span id="clear-bg-btn" class="bg-btn clear-btn" style="display:none;" onclick="clearBg()">Reset</span>
        </div>
    </div>

    <div id="main-content">
        <div id="display-area" style="display:none;"></div>
        <div id="load-more-container" style="display:none;">
            <button id="load-more-btn" class="btn-load-more">Load More</button>
        </div>
        <div id="initial-msg" class="no-data">PLEASE SELECT A MONTH TO BEGIN</div>
    </div>

    <script src="backup_js/manifest.js"></script>

    <script>
        const monthSelect = document.getElementById('month-select');
        const typeFilter = document.getElementById('type-filter');
        const searchInput = document.getElementById('search-input');
        const displayArea = document.getElementById('display-area');
        const loadMoreBtn = document.getElementById('load-more-btn');
        const loadMoreContainer = document.getElementById('load-more-container');
        const initialMsg = document.getElementById('initial-msg');
        const clearBgBtn = document.getElementById('clear-bg-btn');

        let allDataInMonth = [];
        let filteredData = [];
        let currentPage = 0;
        const pageSize = 20;

        // 背景相關功能
        function handleBgUpload(input) {
            const file = input.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    const base64Image = e.target.result;
                    try {
                        localStorage.setItem('plurk_bg_base64', base64Image);
                        applyBg(base64Image);
                    } catch (err) {
                        alert("檔案過大，無法儲存設定！請選擇較小的圖片。");
                    }
                };
                reader.readAsDataURL(file);
            }
        }

        function clearBg() {
            localStorage.removeItem('plurk_bg_base64');
            document.body.style.backgroundImage = 'none';
            document.body.style.backgroundColor = '#ffffff';
            clearBgBtn.style.display = 'none';
        }

        function applyBg(url) {
            if (url) {
                document.body.style.backgroundImage = `url('${url}')`;
                clearBgBtn.style.display = 'inline-block';
            }
        }

        window.onload = function() {
            const savedBg = localStorage.getItem('plurk_bg_base64');
            if (savedBg) applyBg(savedBg);

            if (window.BackupData && window.BackupData.months) {
                window.BackupData.months.forEach(m => {
                    const opt = document.createElement('option');
                    opt.value = m;
                    opt.textContent = m.replace('_', ' / ');
                    monthSelect.appendChild(opt);
                });
            }
        };

        // 資料處理與渲染 (與之前邏輯相同)
        function processData() {
            const type = typeFilter.value;
            const keyword = searchInput.value.toLowerCase().trim();
            filteredData = allDataInMonth.filter(p => {
                const matchType = (type === 'all' || p.plurk_type.toString() === type);
                const matchKeyword = (!keyword || p.content_raw.toLowerCase().includes(keyword));
                return matchType && matchKeyword;
            });
            currentPage = 0;
            displayArea.innerHTML = '';
            displayArea.style.display = 'block';
            renderNextPage();
        }

        function renderNextPage() {
            const start = currentPage * pageSize;
            const end = start + pageSize;
            const pageItems = filteredData.slice(start, end);
            if (pageItems.length === 0 && currentPage === 0) {
                displayArea.innerHTML = '<div class="no-data">NO POSTS FOUND.</div>';
                loadMoreContainer.style.display = 'none';
                return;
            }
            const html = pageItems.map(p => {
                let typeName = (p.plurk_type === 1) ? "Private" : (p.plurk_type === 4 ? "Anonymous" : "Public");
                return `
                    <div class="plurk-item">
                        <div class="item-header">
                            <span class="tag tag-${p.plurk_type}">${typeName}</span>
                            <span class="post-date">${p.posted}</span>
                        </div>
                        <div class="content">${p.content_raw}</div>
                        <div class="footer-links">
                            <a href="${p.plurk_url || '#'}" target="_blank">VIEW ON PLURK →</a>
                        </div>
                    </div>
                `;
            }).join('');
            displayArea.insertAdjacentHTML('beforeend', html);
            currentPage++;
            loadMoreContainer.style.display = (end < filteredData.length) ? 'block' : 'none';
        }

        monthSelect.addEventListener('change', function() {
            const ym = this.value;
            if (!ym) return;
            initialMsg.style.display = 'none';
            displayArea.innerHTML = '<div class="no-data">LOADING...</div>';
            displayArea.style.display = 'block';
            const script = document.createElement('script');
            script.src = `backup_js/${ym}.js`;
            script.onload = () => {
                allDataInMonth = window.BackupData.plurks[ym];
                processData();
            };
            document.head.appendChild(script);
        });

        typeFilter.addEventListener('change', processData);
        searchInput.addEventListener('input', processData);
        loadMoreBtn.addEventListener('click', renderNextPage);
    </script>
</body>
</html>"""

STYLE_CSS_CONTENT = """/* ⚠️ IMPORTANT: Remember to update web_assets.py after editing this file. / 修改後請記得同步更新 web_assets.py。 */
/* --- 基礎設定 --- */
body {
    font-family: "Helvetica Neue", Helvetica, Arial, "PingFang TC", "Microsoft JhengHei", sans-serif;
    color: #1a1a1a; margin: 0; padding: 0;
    background-color: #ffffff;
    background-size: cover;
    background-attachment: fixed;
    background-position: center;
    transition: background-image 0.3s ease-in-out;
    line-height: 1.6;
}

header {
    padding: 80px 20px 40px;
    text-align: center;
    background: transparent;
}

h1 {
    display: inline-block;
    padding: 15px 40px;
    background: rgba(255, 255, 255, 0.4);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border-radius: 10px;
    border: 1px solid rgba(255, 255, 255, 0.3);
    font-size: 2.5em;
    letter-spacing: 8px;
    text-transform: uppercase;
    margin: 0;
    font-weight: 300;
    color: #000;
    text-shadow: 0 1px 10px rgba(255,255,255,0.9);
}

.subtitle {
    display: block;
    margin-top: 15px;
    font-size: 10px;
    letter-spacing: 3px;
    color: #444;
    text-transform: uppercase;
}

/* 導覽列 */
.nav-container {
    border-top: 1px solid #000;
    border-bottom: 1px solid #000;
    display: flex;
    justify-content: center;
    background: rgba(255, 255, 255, 0.85);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    position: sticky;
    top: 0;
    z-index: 100;
    flex-wrap: wrap;
}

.nav-item {
    border-right: 1px solid #000;
    padding: 12px 20px;
    display: flex;
    align-items: center;
    font-size: 11px;
    letter-spacing: 1px;
}

.nav-item:last-child { border-right: none; }

/* 主內容區 */
#main-content {
    max-width: 750px;
    margin: 40px auto;
    padding: 20px;
}

#display-area {
    background: rgba(255, 255, 255, 0.9);
    backdrop-filter: blur(5px);
    -webkit-backdrop-filter: blur(5px);
    padding: 20px 40px;
    box-shadow: 0 4px 15px rgba(0,0,0,0.05);
}

/* 噗文項目樣式 */
.plurk-item {
    margin-bottom: 40px;
    padding-bottom: 30px;
    border-bottom: 1px solid #eee;
}

.content {
    font-size: 16px;
    word-wrap: break-word;
    white-space: pre-wrap;
    color: #222;
}

/* ============================================================
   📱 手機版專屬樣式 (螢幕寬度 600px 以下自動切換)
   ============================================================ */
@media (max-width: 600px) {
    header {
        padding: 40px 15px 20px; /* 縮減頭部高度 */
    }

    h1 {
        font-size: 1.5em;       /* 大幅縮小標題字體 */
        letter-spacing: 4px;    /* 緊縮字距，防止文字溢出 */
        padding: 10px 20px;
        width: 85%;             /* 限制寬度 */
    }

    .nav-container {
        flex-direction: column; /* 導覽列改為垂直排列 */
        position: static;       /* 手機版取消 sticky 避免遮擋空間 */
    }

    .nav-item {
        border-right: none;
        border-bottom: 1px solid rgba(0,0,0,0.1);
        padding: 10px 15px;
        justify-content: space-between;
    }

    #main-content {
        margin: 10px auto;
        padding: 10px;          /* 減少邊界，爭取閱讀空間 */
    }

    #display-area {
        padding: 20px 15px;     /* 縮減內距 */
    }

    .content {
        font-size: 15px;        /* 稍微縮小字體符合小螢幕 */
        line-height: 1.5;
    }

    .item-header {
        flex-wrap: wrap;        /* 讓 meta 資訊在太窄時自動換行 */
        gap: 5px;
    }
}
"""