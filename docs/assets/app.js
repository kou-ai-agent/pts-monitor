// ============================================================
// Config
// ============================================================
const PAGES = [
    { id: 'a' },
    { id: 'b', cat: 'volume',     label: '出来高' },
    { id: 'c', cat: 'price_up',   label: '値上がり率' },
    { id: 'd', cat: 'price_down', label: '値下がり率' },
    { id: 'e', cat: 'turnover',   label: '売買代金' },
];

const SECTOR_WEIGHTS = { volume: 0.40, price_up: 0.25, price_down: 0.25, turnover: 0.10 };

const CAT_LABELS = { volume: '出来高', price_up: '値上がり', price_down: '値下がり', turnover: '売買代金' };

// ============================================================
// State
// ============================================================
let state = {
    availableDates: [],
    currentDate: null,
    currentData: null,
    currentPage: 0,
    chartInstance: null,
    stocksMaster: null,
};

// ============================================================
// DOM
// ============================================================
const DOM = {
    dateSelector:    document.getElementById('date-selector'),
    lastUpdated:     document.getElementById('last-updated'),
    summaryText:     document.getElementById('ai-summary-text'),
    sectorContainer: document.getElementById('sector-container'),
    pageTrack:       document.getElementById('page-track'),
    dots:            document.querySelectorAll('.dot'),
    navLeft:         document.getElementById('nav-left'),
    navRight:        document.getElementById('nav-right'),
    modal:           document.getElementById('chart-modal'),
    modalClose:      document.getElementById('modal-close'),
    modalTitle:      document.getElementById('modal-title'),
    chartCanvas:     document.getElementById('history-chart'),
};

// ============================================================
// Utilities
// ============================================================
const formatNumber = (n) => new Intl.NumberFormat().format(n);
const formatPct    = (n) => (n > 0 ? '+' : '') + n.toFixed(2) + '%';
const formatVolume = (n) => n >= 10000 ? (n / 10000).toFixed(1) + '万' : formatNumber(n);

function getSector(code) {
    const master = state.stocksMaster?.stocks[code];
    if (master?.sector17) return master.sector17;
    // fallback: estimate from code range
    const n = parseInt(code);
    if (isNaN(n)) return 'その他';
    if (n < 1300)  return '水産・農林・鉱業';
    if (n < 2000)  return '建設業';
    if (n < 3000)  return '食料品';
    if (n < 4000)  return '繊維・化学';
    if (n < 5000)  return '医薬品';
    if (n < 6000)  return '素材・金属';
    if (n < 7000)  return '機械・電機';
    if (n < 8000)  return '輸送・精密機器';
    if (n < 8300)  return '商業・卸売';
    if (n < 8600)  return '金融・保険';
    if (n < 9000)  return '不動産';
    if (n < 9300)  return '輸送・電力';
    if (n < 9800)  return '情報・通信';
    return 'サービス';
}

function getMarket(code) {
    return state.stocksMaster?.stocks[code]?.market || '';
}

// ============================================================
// Page Navigation
// ============================================================
function goToPage(idx) {
    if (idx < 0 || idx >= PAGES.length) return;
    state.currentPage = idx;
    DOM.pageTrack.style.transform = `translateX(-${idx * 100}vw)`;
    DOM.dots.forEach((d, i) => d.classList.toggle('active', i === idx));
    DOM.navLeft.classList.toggle('hidden', idx === 0);
    DOM.navRight.classList.toggle('hidden', idx === PAGES.length - 1);
}

// ============================================================
// Swipe (touch)
// ============================================================
let touchStartX = 0;
let touchStartY = 0;

DOM.pageTrack.addEventListener('touchstart', (e) => {
    touchStartX = e.touches[0].clientX;
    touchStartY = e.touches[0].clientY;
}, { passive: true });

DOM.pageTrack.addEventListener('touchend', (e) => {
    const dx = e.changedTouches[0].clientX - touchStartX;
    const dy = e.changedTouches[0].clientY - touchStartY;
    if (Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 50) {
        goToPage(state.currentPage + (dx < 0 ? 1 : -1));
    }
}, { passive: true });

// ============================================================
// Init
// ============================================================
async function init() {
    try {
        // Load stocks master for accurate sector/market lookup (best-effort)
        try {
            const mr = await fetch('data/stocks_master.json');
            if (mr.ok) state.stocksMaster = await mr.json();
        } catch (e) {
            console.warn('stocks_master.json unavailable, using fallback sector logic');
        }

        const res = await fetch(`data/index.json?t=${Date.now()}`);
        if (!res.ok) throw new Error('Index not found');
        const idx = await res.json();
        state.availableDates = idx.dates || [];

        if (state.availableDates.length > 0) {
            populateDateSelector();
            state.currentDate = state.availableDates[0];
            await loadDateData(state.currentDate);
        } else {
            DOM.summaryText.innerText = 'データがありません。';
        }

        DOM.dateSelector.addEventListener('change', (e) => {
            state.currentDate = e.target.value;
            loadDateData(state.currentDate);
        });
        DOM.dots.forEach((dot, i) => dot.addEventListener('click', () => goToPage(i)));
        DOM.navLeft.addEventListener('click',  () => goToPage(state.currentPage - 1));
        DOM.navRight.addEventListener('click', () => goToPage(state.currentPage + 1));
        DOM.modalClose.addEventListener('click', closeModal);
        window.addEventListener('click', (e) => { if (e.target === DOM.modal) closeModal(); });

        goToPage(0);
    } catch (e) {
        console.error(e);
        DOM.summaryText.innerText = 'データの読み込みに失敗しました。';
    }
}

function populateDateSelector() {
    DOM.dateSelector.innerHTML = '';
    state.availableDates.forEach(date => {
        const opt = document.createElement('option');
        opt.value = date;
        opt.textContent = date.replace(/-/g, '/');
        DOM.dateSelector.appendChild(opt);
    });
}

// ============================================================
// Data Loading
// ============================================================
async function loadDateData(dateStr) {
    DOM.summaryText.innerText = '読み込み中...';
    DOM.sectorContainer.innerHTML = '<p class="placeholder-text">読み込み中...</p>';
    ['b', 'c', 'd', 'e'].forEach(p => {
        const el = document.getElementById(`tbody-${p}`);
        if (el) el.innerHTML = '<tr><td colspan="4" style="text-align:center;padding:40px">読み込み中...</td></tr>';
    });

    try {
        const res = await fetch(`data/${dateStr}.json?t=${Date.now()}`);
        if (!res.ok) throw new Error('File not found');
        state.currentData = await res.json();

        const d = state.currentData;
        const timeLabel = d.generated_at ? d.generated_at.slice(0, 5) : '';
        DOM.lastUpdated.textContent = `最終更新: ${d.date} ${timeLabel}`;

        renderAll();
    } catch (e) {
        console.error(e);
        DOM.summaryText.innerText = 'データが見つかりません。';
    }
}

// ============================================================
// Render All Pages
// ============================================================
function renderAll() {
    renderPageA();
    PAGES.slice(1).forEach(({ id, cat }) => renderRankingPage(id, cat));
}

// ============================================================
// Page A: Summary + Sector Scoring
// ============================================================
function renderPageA() {
    const d = state.currentData;
    DOM.summaryText.innerText = d.ai_summary || 'AIサマリーは現在利用できません。';

    if (!d.rankings) return;
    const { sortedSectors, sectorStocks } = computeSectorScores(d.rankings);

    DOM.sectorContainer.innerHTML = '';
    if (sortedSectors.length === 0) {
        DOM.sectorContainer.innerHTML = '<p class="placeholder-text">データがありません。</p>';
        return;
    }

    sortedSectors.forEach(([sector, score], sectorIdx) => {
        const stocks = Object.values(sectorStocks[sector])
            .sort((a, b) => b.totalScore - a.totalScore)
            .slice(0, 5);

        const el = document.createElement('div');
        el.className = 'sector-item';
        el.innerHTML = `
            <div class="sector-header">
                <span class="sector-rank">${sectorIdx + 1}</span>
                <span class="sector-name">${sector}</span>
                <span class="sector-score">${score.toFixed(1)}pt</span>
            </div>
            <div class="sector-stocks">
                ${stocks.map(s => `
                    <div class="sector-stock">
                        <a class="sector-stock-name" href="https://finance.yahoo.co.jp/quote/${s.code}.T" target="_blank" rel="noopener noreferrer">${[getMarket(s.code), s.code, s.name].filter(Boolean).join(' ')}</a>
                        <span class="sector-stock-tags">
                            ${s.appearedIn.map(c => `<span class="tag tag-${c}">${CAT_LABELS[c]}</span>`).join('')}
                        </span>
                        <span class="sector-stock-pct ${s.change_pct > 0 ? 'pct-up' : s.change_pct < 0 ? 'pct-down' : ''}">${formatPct(s.change_pct)}</span>
                    </div>
                `).join('')}
            </div>
        `;
        DOM.sectorContainer.appendChild(el);
    });
}

function computeSectorScores(rankings) {
    const sectorScores  = {};
    const sectorStocks  = {};

    const isEtf = state.stocksMaster
        ? (code) => !state.stocksMaster.stocks[code]          // not in master = ETF/ETN/foreign
        : (code) => /^1\d{3}$/.test(code);                   // fallback: code-range heuristic

    for (const [cat, weight] of Object.entries(SECTOR_WEIGHTS)) {
        const list = (rankings[cat]?.all || []).filter(item => !isEtf(item.code));
        list.slice(0, 10).forEach((item, idx) => {
            const sector = getSector(item.code);
            const score  = (10 - idx) * weight;

            sectorScores[sector] = (sectorScores[sector] || 0) + score;
            if (!sectorStocks[sector]) sectorStocks[sector] = {};
            if (!sectorStocks[sector][item.code]) {
                sectorStocks[sector][item.code] = { ...item, totalScore: 0, appearedIn: [] };
            }
            sectorStocks[sector][item.code].totalScore += score;
            if (!sectorStocks[sector][item.code].appearedIn.includes(cat)) {
                sectorStocks[sector][item.code].appearedIn.push(cat);
            }
        });
    }

    const sortedSectors = Object.entries(sectorScores).sort((a, b) => b[1] - a[1]);
    return { sortedSectors, sectorStocks };
}

// ============================================================
// Pages B–E: Ranking Pages
// ============================================================
function renderRankingPage(pageId, cat) {
    renderPageHighlights(pageId, cat);

    const marketSel = document.getElementById(`market-${pageId}`);
    if (marketSel) {
        marketSel.onchange = () => renderRankingTable(pageId, cat, marketSel.value);
        renderRankingTable(pageId, cat, marketSel.value);
    }
}

function renderPageHighlights(pageId, cat) {
    const container = document.getElementById(`highlights-${pageId}`);
    if (!container) return;

    const highlights = (state.currentData?.ai_highlights || []).filter(h => h.category === cat);
    container.innerHTML = '';

    if (highlights.length === 0) {
        container.innerHTML = '<p class="placeholder-text">このカテゴリの注目銘柄データはありません。</p>';
        return;
    }

    highlights.slice(0, 5).forEach(item => {
        const div = document.createElement('div');
        div.className = 'highlight-item';
        div.innerHTML = `
            <div class="highlight-header">
                <span>${item.name} <span style="font-size:12px;color:var(--text-muted)">(${item.code})</span></span>
            </div>
            <div class="highlight-reason">${item.reason}</div>
        `;
        container.appendChild(div);
    });
}

function renderRankingTable(pageId, cat, market) {
    const tbody = document.getElementById(`tbody-${pageId}`);
    if (!tbody || !state.currentData?.rankings) return;

    let list = [];
    try { list = (state.currentData.rankings[cat][market] || []).filter(item => !/^1\d{3}$/.test(item.code)); } catch (e) {}

    tbody.innerHTML = '';
    if (list.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;padding:40px;color:var(--text-muted)">ランキングデータなし</td></tr>';
        return;
    }

    list.forEach(item => {
        const tr = document.createElement('tr');
        const pctClass  = item.change_pct > 0 ? 'pct-up' : item.change_pct < 0 ? 'pct-down' : '';
        const rankClass = item.rank <= 3 ? 'rank-top3' : '';
        const detailHtml = cat === 'turnover'
            ? `代金<br>${formatVolume(item.turnover / 10000)}億円`
            : `出来高<br>${formatVolume(item.volume)}株`;

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
        tr.addEventListener('click', () => openChart(item.code, item.name, cat, market));
        tbody.appendChild(tr);
    });
}

// ============================================================
// Modal Chart (30-day rank history)
// ============================================================
async function openChart(code, name, category, market) {
    DOM.modalTitle.innerText = `${name} (${code}) ${CAT_LABELS[category] || category} 推移`;
    DOM.modal.classList.add('show');

    const dates = state.availableDates.slice(0, 30).reverse();
    const fetchPromises = dates.map(async d => {
        try {
            const r = await fetch(`data/${d}.json?t=${Date.now()}`);
            if (!r.ok) return { date: d, rank: 101 };
            const json = await r.json();
            const list  = json.rankings?.[category]?.[market] || [];
            const found = list.find(item => item.code === code);
            return { date: d, rank: found ? found.rank : 101 };
        } catch { return { date: d, rank: 101 }; }
    });

    const results   = await Promise.all(fetchPromises);
    const labels    = results.map(r => r.date.substring(5).replace('-', '/'));
    const dataPoints = results.map(r => r.rank);
    renderChart(labels, dataPoints);
}

function renderChart(labels, dataPoints) {
    if (state.chartInstance) state.chartInstance.destroy();
    const ctx = DOM.chartCanvas.getContext('2d');
    state.chartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [{
                label: '順位',
                data: dataPoints,
                borderColor: '#58a6ff',
                backgroundColor: 'rgba(88, 166, 255, 0.1)',
                borderWidth: 2, tension: 0.1, fill: true,
                pointBackgroundColor: '#58a6ff', pointRadius: 4,
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            scales: {
                y: {
                    reverse: true, min: 1, max: 101,
                    ticks: {
                        callback: v => v === 101 ? '圏外' : v + '位',
                        color: '#8b949e', stepSize: 20,
                    },
                    grid: { color: '#30363d' }
                },
                x: { ticks: { color: '#8b949e' }, grid: { color: '#30363d' } }
            },
            plugins: {
                legend: { display: false },
                tooltip: { callbacks: { label: c => c.parsed.y === 101 ? '順位: 圏外' : '順位: ' + c.parsed.y + '位' } }
            }
        }
    });
}

function closeModal() { DOM.modal.classList.remove('show'); }

// ============================================================
// Boot
// ============================================================
document.addEventListener('DOMContentLoaded', init);
