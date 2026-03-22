const UI = {
    dateSelector: document.getElementById('date-selector'),
    marketSelector: document.getElementById('market-selector'),
    categorySelector: document.getElementById('category-selector'),
    summaryText: document.getElementById('ai-summary-text'),
    highlightsContainer: document.getElementById('highlights-container'),
    rankingTbody: document.getElementById('ranking-tbody'),
    modal: document.getElementById('chart-modal'),
    modalClose: document.getElementById('modal-close'),
    modalTitle: document.getElementById('modal-title'),
    chartCanvas: document.getElementById('history-chart'),
};

let state = {
    availableDates: [],
    currentDate: null,
    currentData: null,
    chartInstance: null
};

// ユーティリティ
const formatNumber = (num) => new Intl.NumberFormat().format(num);
const formatPct = (num) => (num > 0 ? '+' : '') + num.toFixed(2) + '%';
const formatVolume = (num) => {
    if (num >= 10000) return (num/10000).toFixed(1) + '万';
    return formatNumber(num);
};

// 初期化
async function init() {
    try {
        const cacheBuster = new Date().getTime();
        const res = await fetch(`../data/index.json?t=${cacheBuster}`);
        if (!res.ok) throw new Error("Index file not found.");
        const idxData = await res.json();
        state.availableDates = idxData.dates || [];
        
        if (state.availableDates.length > 0) {
            populateDateSelector();
            state.currentDate = state.availableDates[0]; 
            await loadDateData(state.currentDate);
        } else {
            UI.summaryText.innerText = "データがありません。";
        }

        // イベントリスナー
        UI.dateSelector.addEventListener('change', (e) => {
            state.currentDate = e.target.value;
            loadDateData(state.currentDate);
        });
        UI.marketSelector.addEventListener('change', renderRankings);
        UI.categorySelector.addEventListener('change', renderRankings);
        UI.modalClose.addEventListener('click', closeModal);
        window.addEventListener('click', (e) => {
            if (e.target === UI.modal) closeModal();
        });

    } catch (e) {
        console.error(e);
        UI.summaryText.innerText = "データの読み込みに失敗しました。";
    }
}

function populateDateSelector() {
    UI.dateSelector.innerHTML = '';
    state.availableDates.forEach(date => {
        const option = document.createElement('option');
        option.value = date;
        option.textContent = date.replace(/-/g, '/');
        UI.dateSelector.appendChild(option);
    });
}

// データの読み込み
async function loadDateData(dateStr) {
    try {
        UI.rankingTbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding: 40px;">読み込み中...</td></tr>';
        
        // ローカル開発時のキャッシュ対策パラメーター
        const cacheBuster = new Date().getTime();
        const res = await fetch(`../data/${dateStr}.json?t=${cacheBuster}`);
        if (!res.ok) throw new Error("File not found");
        
        state.currentData = await res.json();
        
        renderAIContents();
        renderRankings();
    } catch (e) {
        console.error(e);
        UI.summaryText.innerText = "データが見つかりません。";
        UI.highlightsContainer.innerHTML = '';
        UI.rankingTbody.innerHTML = '';
    }
}

// AI情報の描画
function renderAIContents() {
    if (!state.currentData) return;
    
    // サマリー
    if (state.currentData.ai_summary) {
        UI.summaryText.innerText = state.currentData.ai_summary;
    } else {
        UI.summaryText.innerText = "AIサマリーは現在利用できません。";
    }

    // ハイライト
    UI.highlightsContainer.innerHTML = '';
    const hl = state.currentData.ai_highlights || [];
    if (hl.length === 0) {
        UI.highlightsContainer.innerHTML = '<p class="placeholder-text">注目銘柄データはありません。</p>';
    } else {
        hl.forEach(item => {
            const div = document.createElement('div');
            div.className = 'highlight-item';
            div.innerHTML = `
                <div class="highlight-header">
                    <span>${item.name} <span style="font-size:12px;color:var(--text-muted)">(${item.code})</span></span>
                </div>
                <div class="highlight-reason">${item.reason}</div>
            `;
            UI.highlightsContainer.appendChild(div);
        });
    }
}

// ランキングテーブルの描画
function renderRankings() {
    if (!state.currentData || !state.currentData.rankings) return;
    
    const cat = UI.categorySelector.value;
    const mkt = UI.marketSelector.value;
    
    let list = [];
    try {
        list = state.currentData.rankings[cat][mkt] || [];
    } catch(e) {}

    UI.rankingTbody.innerHTML = '';
    
    if (list.length === 0) {
        UI.rankingTbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding: 40px; color:var(--text-muted)">ランキングデータなし</td></tr>';
        return;
    }

    list.forEach(item => {
        const tr = document.createElement('tr');
        
        let pctClass = '';
        if (item.change_pct > 0) pctClass = 'pct-up';
        if (item.change_pct < 0) pctClass = 'pct-down';
        let rankClass = item.rank <= 3 ? 'rank-top3' : '';
        
        // 詳細値
        let detailHtml = '';
        if (cat === 'turnover') {
            detailHtml = `代金<br>${formatVolume(item.turnover / 10000)}億円`;
        } else {
            detailHtml = `出来高<br>${formatVolume(item.volume)}株`;
        }

        tr.innerHTML = `
            <td class="col-rank"><span class="rank-num ${rankClass}">${item.rank}</span></td>
            <td class="col-name">
                <span class="stock-name">${item.name}</span>
                <span class="stock-code">${item.code}</span>
            </td>
            <td class="col-price">
                <span class="price-val">${formatNumber(item.price)}</span>
                <span class="pct-val ${pctClass}">${formatPct(item.change_pct)}</span>
            </td>
            <td class="col-vol">${detailHtml}</td>
        `;

        tr.addEventListener('click', () => openChart(item.code, item.name, cat, mkt));
        UI.rankingTbody.appendChild(tr);
    });
}

// モーダルチャート
async function openChart(code, name, category, market) {
    const categoryName = UI.categorySelector.options[UI.categorySelector.selectedIndex].text;
    UI.modalTitle.innerText = `${name} (${code}) ${categoryName} 推移`;
    UI.modal.classList.add('show');
    
    // 過去30日分のデータを取得して履歴生成
    const dates = state.availableDates.slice(0, 30).reverse(); // 時間の昇順にする
    
    // JSONを並列フェッチ
    const fetchPromises = dates.map(async d => {
        try {
            const cacheBuster = new Date().getTime();
            const r = await fetch(`../data/${d}.json?t=${cacheBuster}`);
            if(!r.ok) return {date: d, rank: 101}; // エラーなら圏外として扱う
            const json = await r.json();
            const list = json.rankings?.[category]?.[market] || [];
            const found = list.find(item => item.code === code);
            return { date: d, rank: found ? found.rank : 101 };
        } catch {
            return { date: d, rank: 101 };
        }
    });
    
    const results = await Promise.all(fetchPromises);
    
    // データ形成
    const labels = results.map(r => r.date.substring(5).replace('-','/')); // "03/20" 形式へ
    const dataPoints = results.map(r => r.rank);

    renderChart(labels, dataPoints);
}

function renderChart(labels, dataPoints) {
    if (state.chartInstance) {
        state.chartInstance.destroy();
    }
    
    const ctx = UI.chartCanvas.getContext('2d');
    state.chartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: '順位',
                data: dataPoints,
                borderColor: '#58a6ff',
                backgroundColor: 'rgba(88, 166, 255, 0.1)',
                borderWidth: 2,
                tension: 0.1,
                fill: true,
                pointBackgroundColor: '#58a6ff',
                pointRadius: 4,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    reverse: true, // 1位が上になるように
                    min: 1,
                    max: 101, // 101を便宜上「圏外」として扱う
                    ticks: {
                        callback: function(value) {
                            if (value === 101) return '圏外';
                            return value + '位';
                        },
                        color: '#8b949e',
                        stepSize: 20
                    },
                    grid: { color: '#30363d' }
                },
                x: {
                    ticks: { color: '#8b949e' },
                    grid: { color: '#30363d' }
                }
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            if (context.parsed.y === 101) return '順位: 圏外';
                            return '順位: ' + context.parsed.y + '位';
                        }
                    }
                }
            }
        }
    });
}

function closeModal() {
    UI.modal.classList.remove('show');
}

// 起動
document.addEventListener('DOMContentLoaded', init);
