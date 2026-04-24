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
    changelog: [],
    view: 'main',       // 'main' | 'changelog'
    menuOpen: false,
};

// ============================================================
// DOM
// ============================================================
const DOM = {
    dateBtn:           document.getElementById('date-btn'),
    lastUpdated:       document.getElementById('last-updated'),
    summaryText:       document.getElementById('ai-summary-text'),
    sectorContainer:   document.getElementById('sector-container'),
    pageTrack:         document.getElementById('page-track'),
    dots:              document.querySelectorAll('.dot'),
    dotNav:            document.getElementById('dot-nav'),
    navLeft:           document.getElementById('nav-left'),
    navRight:          document.getElementById('nav-right'),
    modal:             document.getElementById('chart-modal'),
    modalClose:        document.getElementById('modal-close'),
    modalTitle:        document.getElementById('modal-title'),
    chartCanvas:       document.getElementById('history-chart'),
    logo:              document.getElementById('logo'),
    appMenu:           document.getElementById('app-menu'),
    changelogView:     document.getElementById('changelog-view'),
    changelogContainer:document.getElementById('changelog-container'),
};

const calDOM = {
    btn:         document.getElementById('date-btn'),
    popup:       document.getElementById('calendar-popup'),
    ymBtn:       document.getElementById('cal-ym-btn'),
    prev:        document.getElementById('cal-prev'),
    next:        document.getElementById('cal-next'),
    grid:        document.getElementById('cal-grid'),
    dateDisplay: document.getElementById('cal-date-display'),
    drumOverlay: document.getElementById('cal-drum-overlay'),
    drumYear:    document.getElementById('drum-year'),
    drumMonth:   document.getElementById('drum-month'),
    drumOk:      document.getElementById('drum-ok'),
    drumCancel:  document.getElementById('drum-cancel'),
};

const calState = {
    isOpen:    false,
    viewYear:  2026,
    viewMonth: 4,
    drumYear:  2026,
    drumMonth: 4,
};

const DRUM_ITEM_H = 44;
const DOW_JP = ['日', '月', '火', '水', '木', '金', '土'];

// ============================================================
// Utilities
// ============================================================
const formatNumber = (n) => new Intl.NumberFormat().format(n);
const formatPct    = (n) => (n > 0 ? '+' : '') + n.toFixed(2) + '%';
const formatVolume = (n) => n >= 10000 ? (n / 10000).toFixed(1) + '万' : formatNumber(n);

// ETF/ETN detection: codes absent from stocks_master are funds/foreign listings,
// not regular stocks. Codes in master with sector17='-' are also excluded.
function isEtf(code) {
    if (!state.stocksMaster) return /^1\d{3}$/.test(code);
    const master = state.stocksMaster.stocks[code];
    if (!master) return true;
    return master.sector17 === '-';
}

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
let swipeStartX = 0;
let swipeStartY = 0;
let isSwiping = null; // null=未確定, true=水平スワイプ中, false=垂直スクロール中

function onSwipeTouchStart(e) {
    swipeStartX = e.touches[0].clientX;
    swipeStartY = e.touches[0].clientY;
    isSwiping = null;
}

function onSwipeTouchMove(e) {
    if (isSwiping === null) {
        const dx = Math.abs(e.touches[0].clientX - swipeStartX);
        const dy = Math.abs(e.touches[0].clientY - swipeStartY);
        if (dx > 5 || dy > 5) isSwiping = dx > dy;
    }
    if (isSwiping) e.preventDefault();
}

function onSwipeTouchEnd(e) {
    const dx = e.changedTouches[0].clientX - swipeStartX;
    if (isSwiping && Math.abs(dx) >= 30) {
        goToPage(state.currentPage + (dx < 0 ? 1 : -1));
    }
    isSwiping = null;
}

function onSwipeTouchCancel() {
    isSwiping = null;
}

function initSwipeListeners() {
    const el = DOM.pageTrack;
    el.removeEventListener('touchstart',  onSwipeTouchStart);
    el.removeEventListener('touchmove',   onSwipeTouchMove);
    el.removeEventListener('touchend',    onSwipeTouchEnd);
    el.removeEventListener('touchcancel', onSwipeTouchCancel);
    el.addEventListener('touchstart',  onSwipeTouchStart,  { passive: false });
    el.addEventListener('touchmove',   onSwipeTouchMove,   { passive: false });
    el.addEventListener('touchend',    onSwipeTouchEnd);
    el.addEventListener('touchcancel', onSwipeTouchCancel);
}

initSwipeListeners();

// ============================================================
// Init
// ============================================================
async function init() {
    try {
        // Load changelog (best-effort)
        try {
            const cr = await fetch('data/changelog.json');
            if (cr.ok) state.changelog = await cr.json();
        } catch (e) {}

        // Load stocks master for accurate sector/market lookup (best-effort)
        try {
            const mr = await fetch('data/stocks_master.json');
            if (mr.ok) state.stocksMaster = await mr.json();
        } catch (e) {
            console.warn('stocks_master.json unavailable, using fallback sector logic');
        }

        const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
        const res = await fetch(`data/index.json?t=${Date.now()}`);
        if (!res.ok) throw new Error('Index not found');
        const idx = await res.json();
        state.availableDates = (idx.dates || []).filter(d => DATE_RE.test(d));

        if (state.availableDates.length > 0) {
            state.currentDate = state.availableDates[0];
            calDOM.btn.textContent = state.currentDate.replace(/-/g, '/');
            await loadDateData(state.currentDate);
        } else {
            DOM.summaryText.innerText = 'データがありません。';
        }

        initCalendar();
        DOM.dots.forEach((dot, i) => dot.addEventListener('click', () => goToPage(i)));
        DOM.navLeft.addEventListener('click',  () => goToPage(state.currentPage - 1));
        DOM.navRight.addEventListener('click', () => goToPage(state.currentPage + 1));
        DOM.modalClose.addEventListener('click', closeModal);
        window.addEventListener('click', (e) => { if (e.target === DOM.modal) closeModal(); });

        // Logo menu
        DOM.logo.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleMenu(!state.menuOpen);
        });
        DOM.appMenu.addEventListener('click', (e) => {
            const item = e.target.closest('.app-menu-item');
            if (!item) return;
            toggleMenu(false);
            switchView(item.dataset.view);
        });
        document.addEventListener('click', () => toggleMenu(false));

        goToPage(0);
    } catch (e) {
        console.error(e);
        DOM.summaryText.innerText = 'データの読み込みに失敗しました。';
    }
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

function buildInfoBadges(item) {
    const status = item.external_info_status;
    if (!status) return '';

    const sources = [
        { key: 'tdnet', label: 'TDNET', url: item.tdnet_url },
        { key: 'news',  label: 'ニュース', url: item.news_url },
        { key: 'ir',    label: 'IR',    url: item.ir_url },
    ];

    const badges = sources.map(({ key, label, url }) => {
        const s = status[key];
        if (s === 'found') {
            const href = url ? ` href="${url}" target="_blank" rel="noopener noreferrer"` : '';
            const tag  = url ? 'a' : 'span';
            return `<${tag} class="info-badge info-badge--found"${href}>${label}</${tag}>`;
        } else if (s === 'not_found') {
            return `<span class="info-badge info-badge--not-found">${label}なし</span>`;
        } else if (s === 'error') {
            return `<span class="info-badge info-badge--error">${label}取得不可</span>`;
        }
        return '';
    }).join('');

    return `<div class="info-badges">${badges}</div>`;
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
            ${buildInfoBadges(item)}
        `;
        container.appendChild(div);
    });
}

function renderRankingTable(pageId, cat, market) {
    const tbody = document.getElementById(`tbody-${pageId}`);
    if (!tbody || !state.currentData?.rankings) return;

    let list = [];
    try { list = (state.currentData.rankings[cat][market] || []).filter(item => !isEtf(item.code)); } catch (e) {}

    tbody.innerHTML = '';
    if (list.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;padding:40px;color:var(--text-muted)">ランキングデータなし</td></tr>';
        return;
    }

    list.forEach((item, i) => {
        const tr = document.createElement('tr');
        const displayRank = i + 1;
        const pctClass  = item.change_pct > 0 ? 'pct-up' : item.change_pct < 0 ? 'pct-down' : '';
        const rankClass = displayRank <= 3 ? 'rank-top3' : '';
        const detailHtml = cat === 'turnover'
            ? `代金<br>${formatVolume(item.turnover / 10000)}億円`
            : `出来高<br>${formatVolume(item.volume)}株`;

        tr.innerHTML = `
            <td class="col-rank"><span class="rank-num ${rankClass}">${displayRank}</span></td>
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

// ============================================================
// Menu & View Switching
// ============================================================
function toggleMenu(open) {
    state.menuOpen = open;
    DOM.appMenu.classList.toggle('hidden', !open);
}

function switchView(view) {
    state.view = view;
    const isChangelog = view === 'changelog';
    DOM.changelogView.classList.toggle('hidden', !isChangelog);
    document.querySelector('.page-wrapper').classList.toggle('hidden', isChangelog);
    DOM.dotNav.classList.toggle('hidden', isChangelog);
    // nav arrows: force display:none in changelog mode, restore goToPage logic otherwise
    DOM.navLeft.style.display  = isChangelog ? 'none' : '';
    DOM.navRight.style.display = isChangelog ? 'none' : '';
    if (!isChangelog) goToPage(state.currentPage);
    if (isChangelog) renderChangelog();
}

function renderChangelog() {
    DOM.changelogContainer.innerHTML = '';
    const title = document.createElement('div');
    title.className = 'page-title';
    title.textContent = '更新履歴';
    DOM.changelogContainer.appendChild(title);

    state.changelog.forEach(entry => {
        const el = document.createElement('div');
        el.className = 'changelog-entry';
        el.innerHTML = `
            <div class="changelog-header">
                <span class="changelog-version">${entry.version}</span>
                <span class="changelog-date">${entry.date}</span>
            </div>
            <ul class="changelog-list">
                ${entry.changes.map(c => `<li>${c}</li>`).join('')}
            </ul>
        `;
        DOM.changelogContainer.appendChild(el);
    });
}

function closeModal() { DOM.modal.classList.remove('show'); }

// ============================================================
// Calendar
// ============================================================
function fmtBtn(ds) { return ds.replace(/-/g, '/'); }

function fmtJP(ds) {
    const [y, m, d] = ds.split('-').map(Number);
    return `${y}年${m}月${d}日(${DOW_JP[new Date(y, m - 1, d).getDay()]})`;
}

function openCalendar() {
    if (state.currentDate) {
        const [y, m] = state.currentDate.split('-').map(Number);
        calState.viewYear = y;
        calState.viewMonth = m;
    }
    renderCalendar();
    calDOM.popup.classList.remove('hidden');
    calState.isOpen = true;
}

function closeCalendar() {
    calDOM.popup.classList.add('hidden');
    calState.isOpen = false;
}

function renderCalendar() {
    const { viewYear, viewMonth } = calState;
    calDOM.ymBtn.textContent = `${viewYear}年${viewMonth}月 ›`;

    const firstDow  = (new Date(viewYear, viewMonth - 1, 1).getDay() + 6) % 7; // 0=Mon
    const daysInMon = new Date(viewYear, viewMonth, 0).getDate();
    const today     = new Date(); today.setHours(0, 0, 0, 0);
    const available = new Set(state.availableDates);

    calDOM.grid.innerHTML = '';

    for (let i = 0; i < firstDow; i++) {
        const el = document.createElement('div');
        el.className = 'cal-day';
        calDOM.grid.appendChild(el);
    }

    for (let day = 1; day <= daysInMon; day++) {
        const ds       = `${viewYear}-${String(viewMonth).padStart(2,'0')}-${String(day).padStart(2,'0')}`;
        const cellDate = new Date(viewYear, viewMonth - 1, day);
        const dowMon   = (cellDate.getDay() + 6) % 7; // 0=Mon 5=Sat 6=Sun

        const btn = document.createElement('button');
        btn.className = 'cal-day';
        btn.textContent = day;

        if (cellDate > today || !available.has(ds)) {
            btn.classList.add('disabled');
            btn.disabled = true;
        } else {
            btn.classList.add('available');
            btn.addEventListener('click', (e) => { e.stopPropagation(); selectDay(ds); });
        }
        if (ds === state.currentDate)              btn.classList.add('selected');
        if (cellDate.getTime() === today.getTime()) btn.classList.add('today');
        if (dowMon === 5) btn.classList.add('sat');
        if (dowMon === 6) btn.classList.add('sun');

        calDOM.grid.appendChild(btn);
    }

    if (state.currentDate) setCalFooter(state.currentDate);
}

function selectDay(ds) {
    state.currentDate = ds;
    calDOM.btn.textContent = fmtBtn(ds);
    renderCalendar();
    loadDateData(ds);
    setTimeout(closeCalendar, 150);
}

function setCalFooter(ds) {
    const el = calDOM.dateDisplay;
    el.textContent = fmtJP(ds);
    el.onclick = () => startDateEdit(ds);
}

function startDateEdit(currentDs) {
    const el = calDOM.dateDisplay;
    el.textContent = '';
    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'cal-date-input';
    input.value = currentDs.replace(/-/g, '/');
    input.maxLength = 10;
    el.appendChild(input);
    input.focus();
    input.select();

    let confirmed = false;
    const confirm = () => {
        if (confirmed) return;
        confirmed = true;
        const match = input.value.trim().match(/^(\d{4})\/(\d{2})\/(\d{2})$/);
        if (match) {
            const ds = `${match[1]}-${match[2]}-${match[3]}`;
            if (state.availableDates.includes(ds)) { selectDay(ds); return; }
        }
        setCalFooter(state.currentDate || currentDs);
    };

    input.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); confirm(); } });
    input.addEventListener('blur', confirm);
    input.addEventListener('click', (e) => e.stopPropagation());
}

// ── Drum Roll ──────────────────────────────────────────────
function openDrumRoll() {
    calState.drumYear  = calState.viewYear;
    calState.drumMonth = calState.viewMonth;

    const maxYear = new Date().getFullYear() + 1;
    const years   = [];
    for (let y = 2020; y <= maxYear; y++) years.push({ value: y, label: `${y}年` });
    const months = Array.from({ length: 12 }, (_, i) => ({ value: i + 1, label: `${i + 1}月` }));

    setupDrumCol(calDOM.drumYear,  years,  calState.drumYear - 2020, v => { calState.drumYear  = v; });
    setupDrumCol(calDOM.drumMonth, months, calState.drumMonth - 1,   v => { calState.drumMonth = v; });

    calDOM.drumOverlay.classList.remove('hidden');
}

function closeDrumRoll() {
    calDOM.drumOverlay.classList.add('hidden');
}

function setupDrumCol(el, items, initialIdx, onChange) {
    el.innerHTML = '';

    const pad = () => { const p = document.createElement('div'); p.className = 'drum-pad'; el.appendChild(p); };
    pad(); pad();
    items.forEach((item, i) => {
        const div = document.createElement('div');
        div.className = 'drum-item' + (i === initialIdx ? ' selected' : '');
        div.textContent = item.label;
        el.appendChild(div);
    });
    pad(); pad();

    requestAnimationFrame(() => { el.scrollTop = initialIdx * DRUM_ITEM_H; });

    let timer;
    el.addEventListener('scroll', () => {
        clearTimeout(timer);
        timer = setTimeout(() => {
            const idx = Math.max(0, Math.min(items.length - 1, Math.round(el.scrollTop / DRUM_ITEM_H)));
            onChange(items[idx].value);
            el.querySelectorAll('.drum-item').forEach((d, i) => d.classList.toggle('selected', i === idx));
            el.scrollTo({ top: idx * DRUM_ITEM_H, behavior: 'smooth' });
        }, 80);
    });
}

function initCalendar() {
    calDOM.btn.addEventListener('click', (e) => {
        e.stopPropagation();
        calState.isOpen ? closeCalendar() : openCalendar();
    });

    calDOM.ymBtn.addEventListener('click', (e) => { e.stopPropagation(); openDrumRoll(); });

    calDOM.prev.addEventListener('click', (e) => {
        e.stopPropagation();
        if (--calState.viewMonth < 1)  { calState.viewMonth = 12; calState.viewYear--; }
        renderCalendar();
    });

    calDOM.next.addEventListener('click', (e) => {
        e.stopPropagation();
        if (++calState.viewMonth > 12) { calState.viewMonth = 1;  calState.viewYear++; }
        renderCalendar();
    });

    calDOM.popup.addEventListener('click', (e) => e.stopPropagation());

    calDOM.drumOk.addEventListener('click', () => {
        calState.viewYear  = calState.drumYear;
        calState.viewMonth = calState.drumMonth;
        closeDrumRoll();
        renderCalendar();
    });

    calDOM.drumCancel.addEventListener('click', (e) => { e.stopPropagation(); closeDrumRoll(); });
    calDOM.drumOverlay.addEventListener('click', (e) => { if (e.target === calDOM.drumOverlay) closeDrumRoll(); });

    document.addEventListener('click', () => { if (calState.isOpen) closeCalendar(); });
}

// ============================================================
// Boot
// ============================================================
document.addEventListener('DOMContentLoaded', init);
