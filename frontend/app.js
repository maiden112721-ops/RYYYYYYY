const API_BASE = window.API_BASE_URL ? `${window.API_BASE_URL.replace(/\/$/, '')}/api` : '';
const LOCAL_KEY = 'iloveyoury-demo-data-v1';
let storageMode = 'demo';
const state = { calendarView: 'month', chartView: 'week', date: new Date(), transactionType: 'withdraw', reminders: [], wallets: [], transactions: [] };
const $ = (id) => document.getElementById(id);
const money = (value) => new Intl.NumberFormat('en-PH', { style: 'currency', currency: 'PHP' }).format(Number(value || 0));
const dateText = (value, options = { month: 'short', day: 'numeric' }) => new Intl.DateTimeFormat('en-US', options).format(new Date(value));
function localData() { return JSON.parse(localStorage.getItem(LOCAL_KEY) || '{"letters":[],"reminders":[],"wallets":[],"transactions":[]}'); }
function saveLocal(data) { localStorage.setItem(LOCAL_KEY, JSON.stringify(data)); }
function localId() { return crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`; }
function localResource(path) { return path.split('/')[1]; }
function localWrite(path, body) {
	const data = localData();
	const resource = localResource(path);
	const clientId = body.client_id || localId();
	const now = new Date().toISOString();
	let item;
	if (resource === 'letters') {
		item = { id: clientId, client_id: clientId, title: String(body.title || '').trim(), body_html: String(body.body_html || '').replace(/<(?!\/?(p|br|strong|em|u|s|ul|ol|li|h1|h2|blockquote)\b)[^>]*>/gi, '').trim(), created_at: now };
		if (body.pin !== '091425') throw new Error('That PIN is not quite right.');
		if (!item.title || !item.body_html) throw new Error('Please add a title and letter.');
	} else if (resource === 'reminders') {
		if (new Date(body.end_at) <= new Date(body.start_at)) throw new Error('The reminder must end after it starts.');
		item = { id: clientId, client_id: clientId, title: body.title, description: body.description || '', tags: body.tags || [], start_at: body.start_at, end_at: body.end_at, recurrence: body.recurrence || 'none', created_at: now };
	} else if (resource === 'wallets') {
		item = { id: clientId, client_id: clientId, name: body.name, target: body.target || null, created_at: now };
	} else if (resource === 'transactions') {
		if (!['deposit', 'withdraw'].includes(body.type) || Number(body.amount) <= 0) throw new Error('Enter a valid transaction.');
		item = { id: clientId, client_id: clientId, wallet_id: body.wallet_id || null, type: body.type, amount: body.amount, merchant: body.merchant || '', note: body.note || '', occurred_at: now, _pending: true };
	} else {
		return null;
	}
	item._pending = true;
	data[resource] = data[resource] || [];
	data[resource] = data[resource].filter(existing => existing.client_id !== clientId);
	data[resource].push(item);
	saveLocal(data);
	return item;
}
function mergeLocal(resource, remoteItems) {
	const data = localData();
	const pending = (data[resource] || []).filter(item => item._pending);
	return [...remoteItems, ...pending.filter(item => !remoteItems.some(remote => remote.client_id === item.client_id))];
}
function reconcileLocal(resource, item) {
	const data = localData();
	data[resource] = (data[resource] || []).filter(existing => existing.client_id !== item.client_id);
	data[resource].push({ ...item, _pending: false });
	saveLocal(data);
}
function discardLocal(resource, clientId) {
	const data = localData();
	data[resource] = (data[resource] || []).filter(item => item.client_id !== clientId);
	saveLocal(data);
}
async function retryPending() {
	if (!API_BASE) return;
	const data = localData();
	for (const resource of ['letters', 'reminders', 'wallets', 'transactions']) {
		for (const item of (data[resource] || []).filter(entry => entry._pending)) {
			const body = { ...item };
			delete body.id;
			delete body._pending;
			try {
				const response = await fetch(`${API_BASE}/${resource}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal: AbortSignal.timeout(3500) });
				if (response.ok) reconcileLocal(resource, await response.json());
			} catch (error) {
				return;
			}
		}
	}
}
function localBalance(data, walletId) { return data.transactions.filter(item => item.wallet_id === walletId).reduce((sum, item) => sum + (item.type === 'deposit' ? Number(item.amount) : -Number(item.amount)), 0); }
function localApi(path, options = {}) { const data = localData(); const method = options.method || 'GET'; const body = options.body ? JSON.parse(options.body) : {}; if (path === '/health') return { status: 'ok', service: 'browser-demo' }; if (path === '/letters' && method === 'GET') return [...data.letters].sort((a, b) => b.created_at.localeCompare(a.created_at)); if (path === '/letters' && method === 'POST') { if (body.pin !== '091425') throw new Error('That PIN is not quite right.'); const letter = { id: localId(), title: String(body.title || '').trim(), body_html: String(body.body_html || '').replace(/<(?!\/?(p|br|strong|em|u|s|ul|ol|li|h1|h2|blockquote)\b)[^>]*>/gi, '').trim(), created_at: new Date().toISOString() }; if (!letter.title || !letter.body_html) throw new Error('Please add a title and letter.'); data.letters.push(letter); saveLocal(data); return letter; } if (path === '/reminders' && method === 'GET') return data.reminders; if (path === '/reminders' && method === 'POST') { if (new Date(body.end_at) <= new Date(body.start_at)) throw new Error('The reminder must end after it starts.'); const reminder = { id: localId(), title: body.title, description: body.description || '', tags: body.tags || [], start_at: body.start_at, end_at: body.end_at, recurrence: body.recurrence || 'none', created_at: new Date().toISOString() }; data.reminders.push(reminder); saveLocal(data); return reminder; } if (path.startsWith('/reminders/') && method === 'DELETE') { data.reminders = data.reminders.filter(item => item.id !== path.split('/').pop()); saveLocal(data); return null; } if (path === '/wallets' && method === 'GET') return data.wallets.map(wallet => ({ ...wallet, balance: localBalance(data, wallet.id) })); if (path === '/wallets' && method === 'POST') { const wallet = { id: localId(), name: body.name, target: body.target || null, created_at: new Date().toISOString() }; data.wallets.push(wallet); saveLocal(data); return { ...wallet, balance: 0 }; } if (path === '/transactions' && method === 'GET') return data.transactions; if (path === '/transactions' && method === 'POST') { if (body.wallet_id && !data.wallets.some(wallet => wallet.id === body.wallet_id)) throw new Error('Wallet not found.'); if (body.type === 'withdraw' && Number(body.amount) > localBalance(data, body.wallet_id || null)) throw new Error('This withdrawal is larger than the available balance.'); const transaction = { id: localId(), type: body.type, amount: Number(body.amount), merchant: body.merchant || '', note: body.note || '', wallet_id: body.wallet_id || null, occurred_at: new Date().toISOString() }; data.transactions.push(transaction); saveLocal(data); return transaction; } throw new Error('Demo storage does not support this action yet.'); }
function setStorageMode(mode) { storageMode = mode; const status = $('storageStatus'); if (status) { status.textContent = mode === 'api' ? 'Synced storage' : 'Demo storage'; status.classList.toggle('synced', mode === 'api'); } }
async function api(path, options = {}) {
	const method = options.method || 'GET';
	const body = options.body ? JSON.parse(options.body) : {};
	if (method === 'POST') {
		const localItem = localWrite(path, body);
		if (!API_BASE) return localItem;
		body.client_id = localItem.client_id;
		try {
			const response = await fetch(`${API_BASE}${path}`, { headers: { 'Content-Type': 'application/json' }, signal: AbortSignal.timeout(3500), ...options, body: JSON.stringify(body) });
			const data = await response.json().catch(() => ({}));
			if (!response.ok) throw Object.assign(new Error(data.detail || 'Saved locally; the server could not save this yet.'), { isPermanent: response.status >= 400 && response.status < 500 });
			reconcileLocal(localResource(path), data);
			setStorageMode('api');
			return data;
		} catch (error) {
			if (error.isPermanent) {
				discardLocal(localResource(path), localItem.client_id);
				throw error;
			}
			setStorageMode('demo');
			return localItem;
		}
	}
	if (!API_BASE) return localApi(path, options);
	try {
		const response = await fetch(`${API_BASE}${path}`, { headers: { 'Content-Type': 'application/json' }, signal: AbortSignal.timeout(3500), ...options });
		const data = await response.json().catch(() => ({}));
		if (!response.ok) throw new Error(data.detail || 'Something went wrong.');
		setStorageMode('api');
		return Array.isArray(data) ? mergeLocal(localResource(path), data) : data;
	} catch (error) {
		setStorageMode('demo');
		return localApi(path, options);
	}
}
function toast(message) { $('toast').textContent = message; $('toast').classList.add('show'); setTimeout(() => $('toast').classList.remove('show'), 2600); }
function dialog(id, open = true) { const item = $(id); open ? item.showModal() : item.close(); }
function setupTabs() { document.querySelectorAll('[data-tab]').forEach(button => button.addEventListener('click', () => { document.querySelectorAll('.tab-button').forEach(item => item.classList.toggle('active', item === button)); document.querySelectorAll('.tab-panel').forEach(item => item.classList.toggle('active', item.dataset.panel === button.dataset.tab)); })); }
function renderLetters(items) { const feed = $('letterFeed'); feed.innerHTML = items.length ? items.map((letter, index) => `<article class="letter-card ${index === 0 ? 'featured' : ''}"><div class="letter-meta"><span>${dateText(letter.created_at, { month: 'long', day: 'numeric', year: 'numeric' })}</span><span class="letter-dot">♡</span></div><h2>${escapeHtml(letter.title)}</h2><div class="letter-body">${letter.body_html}</div></article>`).join('') : '<div class="empty-state"><span class="empty-icon">♡</span><h2>Nothing here yet</h2><p>Put the first little love note on the wall.</p></div>'; }
function escapeHtml(value) { const div = document.createElement('div'); div.textContent = value; return div.innerHTML; }
function renderReminders() { const date = state.date; $('calendarTitle').textContent = state.calendarView === 'day' ? dateText(date, { weekday: 'long', month: 'long', day: 'numeric' }) : state.calendarView === 'week' ? `Week of ${dateText(date)}` : dateText(date, { month: 'long', year: 'numeric' }); const calendar = $('calendar'); const matching = state.reminders.filter(item => new Date(item.start_at).toDateString() === date.toDateString() || state.calendarView !== 'day'); if (state.calendarView === 'day') { calendar.innerHTML = `<div class="day-view">${Array.from({ length: 13 }, (_, i) => { const hour = i + 8; const entries = matching.filter(item => new Date(item.start_at).getHours() === hour); return `<div class="time-row"><span>${hour > 12 ? hour - 12 : hour}:00 ${hour >= 12 ? 'PM' : 'AM'}</span><div>${entries.map(reminderHtml).join('')}</div></div>`; }).join('')}</div>`; } else { calendar.innerHTML = `<div class="calendar-grid ${state.calendarView}">${Array.from({ length: state.calendarView === 'week' ? 7 : new Date(date.getFullYear(), date.getMonth() + 1, 0).getDate() }, (_, i) => `<div class="calendar-cell"><span class="day-number">${i + 1}</span>${matching.filter(item => new Date(item.start_at).getDate() === i + 1).map(reminderHtml).join('')}</div>`).join('')}</div>`; } }
function reminderHtml(item) { return `<div class="reminder"><strong>${escapeHtml(item.title)}</strong><small>${(item.tags || []).map(tag => `#${escapeHtml(tag)}`).join(' ')}</small>${state.calendarView !== 'month' ? `<p>${escapeHtml(item.description || '')}</p>` : ''}</div>`; }
function renderWallets() { const balances = state.wallets.map(wallet => Number(wallet.balance || 0)); $('totalBalance').textContent = money(balances.reduce((a, b) => a + b, 0) + state.transactions.filter(t => !t.wallet_id).reduce((sum, t) => sum + (t.type === 'deposit' ? Number(t.amount) : -Number(t.amount)), 0)); $('walletCount').textContent = `${state.wallets.length} wallet${state.wallets.length === 1 ? '' : 's'}`; $('walletGrid').innerHTML = state.wallets.length ? state.wallets.map(wallet => `<button class="wallet-tile" data-wallet="${wallet.id}"><span class="wallet-spark">✦</span><span class="wallet-name">${escapeHtml(wallet.name)}</span><strong>${money(wallet.balance)}</strong>${wallet.target ? `<span class="wallet-target">of ${money(wallet.target)} target</span>` : '<span class="wallet-target">current balance</span>'}</button>`).join('') : '<div class="empty-state compact"><span class="empty-icon">₱</span><h2>Give your money a home</h2><p>Create a wallet for savings, daily life, or dreams.</p></div>'; $('transactionWallet').innerHTML = '<option value="">General balance</option>' + state.wallets.map(wallet => `<option value="${wallet.id}">${escapeHtml(wallet.name)}</option>`).join(''); renderChart(); }
function renderChart() { const filtered = state.transactions.filter(item => item.type === 'withdraw'); const total = filtered.reduce((sum, item) => sum + Number(item.amount), 0); $('chartTotal').textContent = `${money(total)} spent`; const groups = {}; filtered.forEach(item => { const key = dateText(item.occurred_at, state.chartView === 'month' ? { month: 'short' } : { month: 'short', day: 'numeric' }); groups[key] = (groups[key] || 0) + Number(item.amount); }); const values = Object.values(groups); const max = Math.max(...values, 1); $('spendingChart').innerHTML = values.length ? Object.entries(groups).map(([label, value]) => `<div class="bar-wrap"><div class="bar" style="height:${Math.max(value / max * 100, 8)}%" title="${money(value)}"></div><span>${label}</span></div>`).join('') : '<div class="chart-empty">Your spending story will appear here.</div>'; }
async function loadAll() { try { await retryPending(); const [letters, reminders, wallets, transactions] = await Promise.all([api('/letters'), api('/reminders'), api('/wallets'), api('/transactions')]); state.reminders = reminders; state.wallets = wallets; state.transactions = transactions; renderLetters(letters); renderReminders(); renderWallets(); } catch (error) { toast(error.message); } }
function formHandlers() { $('openLetterButton').onclick = () => dialog('pinDialog'); $('pinForm').onsubmit = (event) => { event.preventDefault(); if ($('pinInput').value !== '091425') { $('pinError').textContent = 'That PIN is not quite right.'; return; } dialog('pinDialog', false); $('pinError').textContent = ''; $('pinInput').value = ''; dialog('letterDialog'); }; const editor = new Quill('#letterEditor', { theme: 'snow', modules: { toolbar: [['bold', 'italic', 'underline'], [{ list: 'ordered' }, { list: 'bullet' }], ['blockquote']] } }); $('letterForm').onsubmit = async (event) => { event.preventDefault(); try { await api('/letters', { method: 'POST', body: JSON.stringify({ title: $('letterTitle').value, body_html: editor.root.innerHTML, pin: '091425' }) }); dialog('letterDialog', false); $('letterForm').reset(); editor.setText(''); toast('Your letter is on the wall.'); loadAll(); } catch (error) { $('letterError').textContent = error.message; } }; $('openReminderButton').onclick = () => dialog('reminderDialog'); $('reminderForm').onsubmit = async (event) => { event.preventDefault(); try { await api('/reminders', { method: 'POST', body: JSON.stringify({ title: $('reminderTitle').value, description: $('reminderDescription').value, tags: $('reminderTags').value.split(',').map(item => item.trim()).filter(Boolean), start_at: new Date($('reminderStart').value).toISOString(), end_at: new Date($('reminderEnd').value).toISOString(), recurrence: $('reminderRecurrence').value }) }); dialog('reminderDialog', false); $('reminderForm').reset(); toast('Reminder added.'); loadAll(); } catch (error) { $('reminderError').textContent = error.message; } }; $('openWalletButton').onclick = () => dialog('walletDialog'); $('walletForm').onsubmit = async (event) => { event.preventDefault(); await api('/wallets', { method: 'POST', body: JSON.stringify({ name: $('walletName').value, target: $('walletTarget').value || null }) }); dialog('walletDialog', false); $('walletForm').reset(); toast('New wallet created.'); loadAll(); }; $('openTransactionButton').onclick = () => dialog('transactionDialog'); $('transactionForm').onsubmit = async (event) => { event.preventDefault(); try { await api('/transactions', { method: 'POST', body: JSON.stringify({ type: state.transactionType, amount: $('transactionAmount').value, merchant: $('transactionMerchant').value, wallet_id: $('transactionWallet').value || null }) }); dialog('transactionDialog', false); $('transactionForm').reset(); toast('Transaction saved.'); loadAll(); } catch (error) { $('transactionError').textContent = error.message; } }; document.querySelectorAll('[data-transaction-type]').forEach(button => button.onclick = () => { state.transactionType = button.dataset.transactionType; document.querySelectorAll('[data-transaction-type]').forEach(item => item.classList.toggle('active', item === button)); }); document.querySelectorAll('[data-calendar-view]').forEach(button => button.onclick = () => { state.calendarView = button.dataset.calendarView; document.querySelectorAll('[data-calendar-view]').forEach(item => item.classList.toggle('active', item === button)); renderReminders(); }); document.querySelectorAll('[data-chart-view]').forEach(button => button.onclick = () => { state.chartView = button.dataset.chartView; document.querySelectorAll('[data-chart-view]').forEach(item => item.classList.toggle('active', item === button)); renderChart(); }); $('prevDate').onclick = () => { state.date.setDate(state.date.getDate() - (state.calendarView === 'week' ? 7 : 1)); renderReminders(); }; $('nextDate').onclick = () => { state.date.setDate(state.date.getDate() + (state.calendarView === 'week' ? 7 : 1)); renderReminders(); }; }
let googleToken = '';
const googleExported = new Set();
function setIntegrationStatus(id, message, connected = false) { const item = $(id); item.querySelector('span:nth-child(2)').textContent = message; item.classList.toggle('connected', connected); }
function requestGoogleToken() { return new Promise((resolve, reject) => { if (!window.GOOGLE_CLIENT_ID) return reject(new Error('Add GOOGLE_CLIENT_ID in frontend/config.js first.')); if (!window.google?.accounts?.oauth2) return reject(new Error('Google sign-in is still loading. Try again in a moment.')); const client = window.google.accounts.oauth2.initTokenClient({ client_id: window.GOOGLE_CLIENT_ID, scope: 'https://www.googleapis.com/auth/calendar', callback: response => response.error ? reject(new Error('Google Calendar permission was not granted.')) : resolve(response.access_token) }); client.requestAccessToken({ prompt: googleToken ? '' : 'consent' }); }); }
async function googleCalendarRequest(path, options = {}) { if (!googleToken) googleToken = await requestGoogleToken(); const response = await fetch(`https://www.googleapis.com/calendar/v3${path}`, { ...options, headers: { Authorization: `Bearer ${googleToken}`, 'Content-Type': 'application/json', ...(options.headers || {}) } }); if (response.status === 401) { googleToken = ''; throw new Error('Google Calendar permission expired. Connect again.'); } if (!response.ok) throw new Error('Google Calendar could not complete that request.'); return response.json(); }
async function connectGoogleCalendar() { try { await requestGoogleToken(); setIntegrationStatus('googleCalendarStatus', 'Google Calendar connected for this browser', true); toast('Google Calendar connected.'); } catch (error) { toast(error.message); } }
async function importGoogleEvents() { try { const start = new Date(); start.setMonth(start.getMonth() - 1); const result = await googleCalendarRequest(`/calendars/primary/events?singleEvents=true&orderBy=startTime&timeMin=${encodeURIComponent(start.toISOString())}`); let imported = 0; for (const event of result.items || []) { if (!event.start?.dateTime || !event.end?.dateTime || googleExported.has(event.id)) continue; await api('/reminders', { method: 'POST', body: JSON.stringify({ title: event.summary || 'Google Calendar event', description: event.description || '', tags: ['google'], start_at: event.start.dateTime, end_at: event.end.dateTime, recurrence: 'none' }) }); googleExported.add(event.id); imported += 1; } await loadAll(); setIntegrationStatus('googleCalendarStatus', `Google Calendar connected · ${imported} event${imported === 1 ? '' : 's'} imported`, true); } catch (error) { toast(error.message); } }
async function exportGoogleEvents() { try { let exported = 0; for (const reminder of state.reminders) { if (googleExported.has(reminder.id)) continue; const event = await googleCalendarRequest('/calendars/primary/events', { method: 'POST', body: JSON.stringify({ summary: reminder.title, description: reminder.description || '', start: { dateTime: reminder.start_at }, end: { dateTime: reminder.end_at } }) }); googleExported.add(reminder.id); googleExported.add(event.id); exported += 1; } setIntegrationStatus('googleCalendarStatus', `Google Calendar connected · ${exported} reminder${exported === 1 ? '' : 's'} exported`, true); toast('Reminders sent to Google Calendar.'); } catch (error) { toast(error.message); } }
function csvCell(value) { return `"${String(value ?? '').replaceAll('"', '""')}"`; }
async function exportCashewCsv() { try { const items = await api('/transactions'); const csv = ['type,amount,merchant,occurred_at,wallet_id', ...items.map(item => [item.type, item.amount, item.merchant, item.occurred_at, item.wallet_id || ''].map(csvCell).join(','))].join('\n'); const link = document.createElement('a'); link.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' })); link.download = 'iloveyoury-transactions.csv'; link.click(); URL.revokeObjectURL(link.href); toast('Transaction CSV exported.'); } catch (error) { toast(error.message); } }
function parseCsvLine(line) { const cells = []; let value = ''; let quoted = false; for (let index = 0; index < line.length; index += 1) { const char = line[index]; if (char === '"' && line[index + 1] === '"') { value += '"'; index += 1; } else if (char === '"') quoted = !quoted; else if (char === ',' && !quoted) { cells.push(value); value = ''; } else value += char; } cells.push(value); return cells; }
async function importCashewCsv(file) { const lines = (await file.text()).split(/\r?\n/).filter(Boolean); if (lines.length < 2) throw new Error('That CSV has no transactions.'); const headers = parseCsvLine(lines[0]); let imported = 0; for (const line of lines.slice(1)) { const row = Object.fromEntries(parseCsvLine(line).map((value, index) => [headers[index], value])); if (!['deposit', 'withdraw'].includes(row.type) || !Number(row.amount)) continue; await api('/transactions', { method: 'POST', body: JSON.stringify({ type: row.type, amount: row.amount, merchant: row.merchant || 'Cashew import', wallet_id: row.wallet_id || null }) }); imported += 1; } await loadAll(); toast(`${imported} Cashew transaction${imported === 1 ? '' : 's'} imported.`); }
function setupIntegrations() { $('googleCalendarButton').onclick = connectGoogleCalendar; $('googleCalendarStatus').insertAdjacentHTML('beforeend', '<button class="text-button" id="googleImportButton">Import</button><button class="text-button" id="googleExportButton">Export</button>'); $('googleImportButton').onclick = importGoogleEvents; $('googleExportButton').onclick = exportGoogleEvents; $('cashewButton').onclick = () => { window.open(window.CASHEW_URL || 'https://cashewapp.web.app/', '_blank', 'noopener'); toast('Cashew opened. Use CSV exchange here when ready.'); }; $('cashewImportButton').onclick = () => $('cashewFile').click(); $('cashewFile').onchange = async event => { try { if (event.target.files[0]) await importCashewCsv(event.target.files[0]); } catch (error) { toast(error.message); } event.target.value = ''; }; $('cashewExportButton').onclick = exportCashewCsv; }
setupTabs(); formHandlers(); setupIntegrations(); $('todayLabel').textContent = dateText(new Date(), { weekday: 'long', month: 'long', day: 'numeric' }); loadAll();
window.addEventListener('online', () => { retryPending().then(loadAll); });