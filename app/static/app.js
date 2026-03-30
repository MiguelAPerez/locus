// -- Auth state -------------------------------------------------------------
let authToken = localStorage.getItem('locus_token') || null;
let authEnabled = false;
let isAdmin = false;
let isApiKeyAuth = false;

async function checkAuth() {
  const r = await fetch('/auth/status');
  const data = await r.json();
  authEnabled = data.auth_enabled;
  if (authEnabled) {
    document.getElementById('logoutBtn').classList.remove('hidden');
    if (!data.registration_enabled) {
      document.getElementById('registerBtn').classList.add('hidden');
    }
    if (!authToken) { showLoginPage(); return false; }
    try {
      const me = await api('GET', '/auth/me');
      isAdmin = me.is_admin || false;
      isApiKeyAuth = me.is_api_key || false;
    } catch (_) {
      return false; // api() already redirected to login
    }
  }
  return true;
}

function showLoginPage() {
  showSignInForm();
  document.getElementById('loginPage').classList.remove('hidden');
}

function hideLoginPage() {
  document.getElementById('loginPage').classList.add('hidden');
}

function showSignInForm() {
  document.getElementById('loginSignInForm').classList.remove('hidden');
  document.getElementById('loginResetForm').classList.add('hidden');
  document.getElementById('loginError').textContent = '';
}

function showResetTokenForm() {
  document.getElementById('loginSignInForm').classList.add('hidden');
  document.getElementById('loginResetForm').classList.remove('hidden');
  document.getElementById('resetError').textContent = '';
}

async function doResetPassword() {
  const token = document.getElementById('resetTokenInput').value.trim();
  const newPassword = document.getElementById('resetNewPassword').value;
  const err = document.getElementById('resetError');
  err.textContent = '';
  if (!token) { err.textContent = 'Paste your reset token'; return; }
  const r = await fetch('/auth/reset-password', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token, new_password: newPassword }),
  });
  if (r.status === 400) {
    const d = await r.json().catch(() => ({}));
    err.textContent = d.detail || 'Invalid or expired token';
    return;
  }
  if (!r.ok) { err.textContent = 'Reset failed'; return; }
  // Password changed — log in with new password
  document.getElementById('loginPassword').value = newPassword;
  showSignInForm();
  document.getElementById('loginError').textContent = 'Password updated — sign in with your new password';
}

async function doLogin() {
  const username = document.getElementById('loginUsername').value.trim();
  const password = document.getElementById('loginPassword').value;
  const err = document.getElementById('loginError');
  const btn = document.getElementById('signInBtn');
  err.textContent = '';
  btn.disabled = true;
  btn.textContent = 'Signing in…';
  try {
    const r = await fetch('/auth/login', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    if (!r.ok) { err.textContent = 'Invalid username or password'; return; }
    authToken = (await r.json()).access_token;
    localStorage.setItem('locus_token', authToken);
    hideLoginPage();
    init();
  } finally {
    btn.disabled = false;
    btn.textContent = 'Sign in';
  }
}

async function doRegister() {
  const username = document.getElementById('loginUsername').value.trim();
  const password = document.getElementById('loginPassword').value;
  const err = document.getElementById('loginError');
  err.textContent = '';
  const r = await fetch('/auth/register', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (r.status === 409) { err.textContent = 'Username already taken'; return; }
  if (r.status === 403) { err.textContent = 'Registration is disabled'; return; }
  if (!r.ok) { err.textContent = 'Registration failed'; return; }
  await doLogin();
}

function doLogout() {
  authToken = null;
  localStorage.removeItem('locus_token');
  if (authEnabled) showLoginPage();
}

// -- Change password --------------------------------------------------------
async function changePassword() {
  const current = document.getElementById('currentPassword').value;
  const next = document.getElementById('newPassword').value;
  const status = document.getElementById('changePasswordStatus');
  status.innerHTML = '';
  try {
    await api('POST', '/auth/change-password', { current_password: current, new_password: next });
    document.getElementById('currentPassword').value = '';
    document.getElementById('newPassword').value = '';
    status.innerHTML = `<span class="${STATUS_OK}">Password updated.</span>`;
  } catch (e) {
    status.innerHTML = `<span class="${STATUS_ERR}">${esc(e.message)}</span>`;
  }
}

// -- Users panel (admin) ----------------------------------------------------
async function loadUsers() {
  if (!authEnabled || !isAdmin) return;
  document.getElementById('usersSection').classList.remove('hidden');
  const { users } = await api('GET', '/auth/users');
  const list = document.getElementById('usersList');
  list.innerHTML = users.map(u => {
    const isSelf = u.username === (document.getElementById('logoutBtn') ? '__self__' : '');
    return `
    <div class="flex items-center justify-between text-xs py-1 gap-2">
      <span class="text-text flex-1">${esc(u.username)}${u.is_admin ? ' <span class="text-accent">[admin]</span>' : ''}</span>
      <button onclick="resetUserPassword('${esc(u.id)}')" class="text-muted hover:text-accent hover:underline">Reset</button>
      <button onclick="toggleAdmin('${esc(u.id)}', ${u.is_admin})" class="text-muted hover:text-accent2 hover:underline">${u.is_admin ? 'Demote' : 'Promote'}</button>
      <button onclick="deleteUser('${esc(u.id)}')" class="text-danger hover:opacity-85 ml-1">✕</button>
    </div>`;
  }).join('');
}

async function resetUserPassword(userId) {
  try {
    const { reset_token } = await api('POST', `/auth/users/${userId}/reset-password`);
    document.getElementById('resetTokenValue').textContent = reset_token;
    document.getElementById('resetTokenDisplay').classList.remove('hidden');
  } catch (e) {
    alert(e.message);
  }
}

async function toggleAdmin(userId, currentlyAdmin) {
  try {
    await api('POST', `/auth/users/${userId}/${currentlyAdmin ? 'demote' : 'promote'}`);
    loadUsers();
  } catch (e) {
    alert(e.message);
  }
}

async function deleteUser(userId) {
  if (!confirm('Delete this user? Their data will remain on disk.')) return;
  try {
    await api('DELETE', `/auth/users/${userId}`);
    loadUsers();
  } catch (e) {
    alert(e.message);
  }
}

function copyResetToken() {
  navigator.clipboard.writeText(document.getElementById('resetTokenValue').textContent);
}

function dismissResetToken() {
  document.getElementById('resetTokenDisplay').classList.add('hidden');
  document.getElementById('resetTokenValue').textContent = '';
}

// -- API keys panel ---------------------------------------------------------
async function loadApiKeys() {
  if (!authEnabled) return;
  document.getElementById('apiKeysSection').classList.remove('hidden');
  const { keys } = await api('GET', '/auth/keys');
  const list = document.getElementById('apiKeysList');
  list.innerHTML = keys.map(k => `
    <div class="flex items-center justify-between text-xs py-1">
      <span class="text-text">${esc(k.name)} <span class="text-muted">(${esc(k.key_prefix)}…)</span></span>
      <button onclick="deleteApiKey('${esc(k.id)}')" class="text-red-400 hover:text-red-300 ml-2">✕</button>
    </div>`).join('');
}

async function showCreateKeyForm() {
  document.getElementById('createKeyForm').classList.remove('hidden');
  const spacesList = document.getElementById('newKeySpacesList');
  const collsList = document.getElementById('newKeyCollectionsList');
  spacesList.innerHTML = '<span class="text-[0.65rem] text-muted">Loading…</span>';
  collsList.innerHTML = '<span class="text-[0.65rem] text-muted">Loading…</span>';

  try {
    const [{ spaces }, { collections }] = await Promise.all([
      api('GET', '/spaces'),
      api('GET', '/collections')
    ]);

    const renderBox = (name, type) => `
      <label class="flex items-center gap-2 hover:bg-white/5 px-1 rounded cursor-pointer group">
        <input type="checkbox" name="newKey${type}" value="${esc(name)}" class="accent-accent w-3 h-3" />
        <span class="text-[0.8rem] text-text/80 group-hover:text-text truncate">${esc(name)}</span>
      </label>`;

    spacesList.innerHTML = spaces.length ? spaces.map(s => renderBox(s, 'Space')).join('') : '<span class="text-[0.65rem] text-muted p-1">No spaces found.</span>';
    collsList.innerHTML = collections.length ? collections.map(c => renderBox(c, 'Coll')).join('') : '<span class="text-[0.65rem] text-muted p-1">No collections found.</span>';
  } catch (e) {
    spacesList.innerHTML = collsList.innerHTML = `<span class="text-danger text-[0.65rem] p-1">${esc(e.message)}</span>`;
  }
}

async function createApiKey() {
  const nameInput = document.getElementById('newKeyName');
  const name = nameInput.value.trim();
  if (!name) return;

  const allowed_spaces = Array.from(document.querySelectorAll('input[name="newKeySpace"]:checked')).map(cb => cb.value);
  const allowed_collections = Array.from(document.querySelectorAll('input[name="newKeyColl"]:checked')).map(cb => cb.value);

  try {
    const data = await api('POST', '/auth/keys', { name, allowed_spaces, allowed_collections });
    document.getElementById('createKeyForm').classList.add('hidden');
    document.getElementById('newKeyValue').textContent = data.key;
    document.getElementById('newKeyDisplay').classList.remove('hidden');
    nameInput.value = '';
    loadApiKeys();
  } catch (e) {
    alert(e.message);
  }
}

async function deleteApiKey(id) {
  await api('DELETE', `/auth/keys/${id}`);
  loadApiKeys();
}

function copyApiKey() {
  navigator.clipboard.writeText(document.getElementById('newKeyValue').textContent);
}

function dismissApiKey() {
  document.getElementById('newKeyDisplay').classList.add('hidden');
  document.getElementById('newKeyValue').textContent = '';
}

// -- Init ------------------------------------------------------------------
let currentSpace = null;
let currentCollection = null;

const SPACE_ITEM_BASE   = 'group px-3 py-1.5 rounded cursor-pointer text-sm border border-transparent flex justify-between items-center hover:bg-surface';
const SPACE_ITEM_ACTIVE = 'group px-3 py-1.5 rounded cursor-pointer text-sm border flex justify-between items-center bg-surface border-accent text-accent';
const BTN_PRIMARY   = 'bg-accent text-white border-none rounded px-3 py-1.5 text-[0.8rem] cursor-pointer font-semibold hover:opacity-85';
const BTN_SECONDARY = 'bg-surface border border-border text-text rounded px-3 py-1.5 text-[0.8rem] cursor-pointer hover:opacity-85';
const BTN_DANGER    = 'bg-danger text-white border-none rounded px-2 py-0.5 text-[0.7rem] cursor-pointer font-semibold hover:opacity-85';
const STATUS_OK     = 'text-[0.8rem] px-3 py-1.5 rounded bg-[#0d2e22] text-success';
const STATUS_ERR    = 'text-[0.8rem] px-3 py-1.5 rounded bg-[#2e0d0d] text-danger';
const TAG           = 'inline-block text-[0.7rem] px-1.5 py-0.5 rounded bg-border text-muted';

function sourceBadgeClass(source) {
  const base = 'text-[0.65rem] px-1.5 py-0.5 rounded-[3px]';
  if (source === 'env')   return base + ' bg-[#1a2e1a] text-success';
  if (source === 'saved') return base + ' bg-[#1a1e2e] text-accent';
  return base + ' bg-border text-muted';
}

async function api(method, path, body) {
  const opts = { method, headers: {} };
  if (authToken) opts.headers['Authorization'] = `Bearer ${authToken}`;
  if (body instanceof FormData) {
    opts.body = body;
  } else if (body) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  const r = await fetch(path, opts);
  if (r.status === 401) {
    authToken = null;
    localStorage.removeItem('locus_token');
    if (authEnabled) showLoginPage();
    throw new Error('Unauthorized');
  }
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(err.detail || r.statusText);
  }
  return r.status === 204 ? null : r.json();
}

async function loadSpaces() {
  const { spaces } = await api('GET', '/spaces');
  const list = document.getElementById('spaceList');
  list.innerHTML = '';
  for (const s of spaces) {
    const el = document.createElement('div');
    el.className = s === currentSpace ? SPACE_ITEM_ACTIVE : SPACE_ITEM_BASE;
    const nameSpan = document.createElement('span');
    nameSpan.textContent = s;
    el.appendChild(nameSpan);
    const deleteSpan = document.createElement('span');
    deleteSpan.className = 'opacity-0 group-hover:opacity-100 text-xs text-danger cursor-pointer';
    deleteSpan.textContent = '✕';
    deleteSpan.addEventListener('click', e => delSpace(e, s));
    el.appendChild(deleteSpan);
    el.addEventListener('click', () => selectSpace(s));
    list.appendChild(el);
  }
}

async function loadCollections() {
  const { collections } = await api('GET', '/collections');
  const list = document.getElementById('collectionList');
  list.innerHTML = '';
  for (const c of collections) {
    const el = document.createElement('div');
    el.className = c === currentCollection ? SPACE_ITEM_ACTIVE : SPACE_ITEM_BASE;
    const nameSpan = document.createElement('span');
    nameSpan.textContent = c;
    el.appendChild(nameSpan);
    const deleteSpan = document.createElement('span');
    deleteSpan.className = 'opacity-0 group-hover:opacity-100 text-xs text-danger cursor-pointer';
    deleteSpan.textContent = '✕';
    deleteSpan.addEventListener('click', e => delCollection(e, c));
    el.appendChild(deleteSpan);
    el.addEventListener('click', () => selectCollection(c));
    list.appendChild(el);
  }
}

async function createCollection() {
  const input = document.getElementById('newCollectionName');
  const name = input.value.trim();
  if (!name) return;
  try {
    await api('POST', '/collections', { name });
    input.value = '';
    loadCollections();
  } catch (e) { alert(e.message); }
}

async function delCollection(e, name) {
  e.stopPropagation();
  if (!confirm(`Delete collection "${name}"? (spaces are not affected)`)) return;
  await api('DELETE', `/collections/${name}`);
  if (currentCollection === name) { currentCollection = null; renderEmpty(); }
  loadCollections();
}

function selectCollection(name) {
  currentCollection = name;
  currentSpace = null;
  loadSpaces();
  loadCollections();
  renderCollection(name);
}

async function renderCollection(name) {
  const collection = await api('GET', `/collections/${name}`);
  const { spaces: allSpaces } = await api('GET', '/spaces');
  const members = collection.spaces;
  const nonMembers = allSpaces.filter(s => !members.includes(s));

  document.getElementById('main').innerHTML = `
    <div class="flex items-center gap-2 mb-1">
      <span class="text-[0.7rem] uppercase tracking-[0.1em] text-muted">Collection</span>
      <span class="text-accent font-semibold">${esc(name)}</span>
    </div>

    <div class="bg-surface border border-border rounded p-4 px-5">
      <h3 class="text-[0.8rem] uppercase tracking-[0.08em] text-muted mb-3">Members</h3>
      <div id="membersList" class="flex flex-col gap-1.5 mb-3">
        ${members.length === 0
          ? '<span class="text-muted text-[0.8rem]">No spaces yet.</span>'
          : members.map(s => `
            <div class="flex justify-between items-center text-[0.8rem] py-1 border-b border-border">
              <span class="text-text">${esc(s)}</span>
              <button class="${BTN_DANGER}" data-remove-space="${esc(s)}">remove</button>
            </div>`).join('')}
      </div>
      ${nonMembers.length > 0 ? `
      <div class="flex gap-2 items-center">
        <select id="addSpaceSelect" class="flex-1 bg-bg border border-border rounded px-2.5 py-1.5 text-text text-[0.8rem] outline-none focus:border-accent">
          ${nonMembers.map(s => `<option value="${esc(s)}">${esc(s)}</option>`).join('')}
        </select>
        <button class="${BTN_PRIMARY}" onclick="addToCollection()">Add space</button>
      </div>` : '<span class="text-muted text-xs">All spaces are already members.</span>'}
    </div>

    <div class="bg-surface border border-border rounded p-4 px-5">
      <h3 class="text-[0.8rem] uppercase tracking-[0.08em] text-muted mb-3">Search across collection</h3>
      <div class="flex gap-2">
        <input id="colSearchQ" placeholder="Ask anything…" class="flex-1 bg-bg border border-border rounded px-3 py-2 text-text text-sm outline-none focus:border-accent" onkeydown="if(event.key==='Enter') doCollectionSearch()" />
        <input type="number" id="colSearchK" value="5" min="1" max="50" class="w-[60px] bg-bg border border-border rounded p-2 text-text outline-none" title="top-k" />
        <button class="${BTN_PRIMARY}" onclick="doCollectionSearch()">Search</button>
      </div>
      <div id="colSearchResults" class="mt-4"></div>
    </div>`;

  document.getElementById('membersList')?.querySelectorAll('[data-remove-space]').forEach(btn => {
    btn.addEventListener('click', () => removeFromCollection(btn.dataset.removeSpace));
  });
}

async function addToCollection() {
  const select = document.getElementById('addSpaceSelect');
  const space = select?.value;
  if (!space || !currentCollection) return;
  try {
    await api('POST', `/collections/${currentCollection}/spaces/${space}`);
    renderCollection(currentCollection);
  } catch (e) { alert(e.message); }
}

async function removeFromCollection(space) {
  if (!currentCollection) return;
  try {
    await api('DELETE', `/collections/${currentCollection}/spaces/${space}`);
    renderCollection(currentCollection);
  } catch (e) { alert(e.message); }
}

async function doCollectionSearch() {
  if (!currentCollection) return;
  const q = document.getElementById('colSearchQ').value.trim();
  if (!q) return;
  const k = document.getElementById('colSearchK').value;
  const el = document.getElementById('colSearchResults');
  el.innerHTML = '<span class="text-muted text-[0.8rem]">Searching…</span>';
  try {
    const data = await api('GET', `/collections/${currentCollection}/search?q=${encodeURIComponent(q)}&k=${k}`);
    if (!data.results.length) { el.innerHTML = '<span class="text-muted text-[0.8rem]">No results.</span>'; return; }
    el.innerHTML = `<div class="flex flex-col gap-3">${data.results.map(r => `
      <div class="bg-bg border border-border rounded px-4 py-3">
        <div class="flex justify-between text-xs text-muted mb-1.5">
          <div class="flex gap-1.5">
            <span class="${TAG} text-accent">${esc(r.space)}</span>
            <span class="${TAG}">${esc(r.metadata?.filename || r.metadata?.source || 'doc')}</span>
          </div>
          <span class="text-accent2 font-semibold">score ${r.score}</span>
        </div>
        <div class="text-sm leading-relaxed">${esc(r.text)}</div>
      </div>`).join('')}</div>`;
  } catch (e) {
    el.innerHTML = `<span class="text-danger text-[0.8rem]">${esc(e.message)}</span>`;
  }
}

async function createSpace() {
  const input = document.getElementById('newSpaceName');
  const name = input.value.trim();
  if (!name) return;
  try {
    await api('POST', '/spaces', { name });
    input.value = '';
    loadSpaces();
  } catch (e) { alert(e.message); }
}

async function delSpace(e, name) {
  e.stopPropagation();
  if (!confirm(`Delete space "${name}" and all its data?`)) return;
  await api('DELETE', `/spaces/${name}`);
  if (currentSpace === name) { currentSpace = null; renderEmpty(); }
  loadSpaces();
}

function selectSpace(name) {
  currentSpace = name;
  currentCollection = null;
  loadSpaces();
  loadCollections();
  renderSpace();
}

function renderEmpty() {
  document.getElementById('main').innerHTML = `
    <div class="flex flex-col items-center justify-center flex-1 text-muted gap-2 p-16 text-center">
      <div class="text-[2.5rem]">◈</div>
      <div>Select or create a dataspace to get started</div>
    </div>`;
}

function renderSpace() {
  document.getElementById('main').innerHTML = `
    <div class="bg-surface border border-border rounded p-4 px-5">
      <h3 class="text-[0.8rem] uppercase tracking-[0.08em] text-muted mb-3">Search</h3>
      <div class="flex gap-2">
        <input id="searchQ" placeholder="Ask anything…" class="flex-1 bg-bg border border-border rounded px-3 py-2 text-text text-sm outline-none focus:border-accent" onkeydown="if(event.key==='Enter') doSearch()" />
        <input type="number" id="searchK" value="5" min="1" max="50" class="w-[60px] bg-bg border border-border rounded p-2 text-text outline-none" title="top-k" />
        <label class="text-[0.8rem] flex items-center gap-1 text-muted">
          <input type="checkbox" id="searchFull" /> full
        </label>
        <button class="${BTN_PRIMARY}" onclick="doSearch()">Search</button>
      </div>
      <div id="searchResults" class="mt-4"></div>
    </div>

    <div class="bg-surface border border-border rounded p-4 px-5">
      <h3 class="text-[0.8rem] uppercase tracking-[0.08em] text-muted mb-3">Ingest</h3>
      <div class="flex flex-col gap-2">
        <textarea id="ingestText" placeholder="Paste text to ingest…" class="bg-bg border border-border rounded px-3 py-2.5 text-text text-sm resize-y min-h-[90px] font-sans outline-none focus:border-accent"></textarea>
        <div class="flex gap-2 items-center">
          <input type="text" id="ingestSource" placeholder="source label (optional)" class="flex-1 bg-bg border border-border rounded px-2.5 py-1.5 text-text text-[0.8rem] outline-none focus:border-accent" />
          <button class="${BTN_PRIMARY}" onclick="doIngest()">Ingest</button>
        </div>
        <div class="text-muted text-xs">or upload a file:</div>
        <div class="flex gap-2 items-center">
          <input type="file" id="ingestFile" accept=".txt,.md,.markdown,.csv,.json,.pdf,.png,.jpg,.jpeg,.gif,.webp,.tiff,.bmp,.mp3,.wav,.ogg,.m4a,.flac,.webm,text/*,application/pdf,image/*,audio/*" class="flex-1 text-[0.8rem] text-muted" />
          <button class="${BTN_PRIMARY}" onclick="doUpload()">Upload</button>
        </div>
        <div id="ingestStatus"></div>
      </div>
    </div>

    <div class="bg-surface border border-border rounded p-4 px-5">
      <h3 class="text-[0.8rem] uppercase tracking-[0.08em] text-muted mb-3">Documents</h3>
      <div id="docsList"><span class="text-muted text-[0.8rem]">Loading…</span></div>
      <button class="bg-surface border border-border text-text rounded px-3 py-1.5 text-xs cursor-pointer hover:opacity-85 mt-3" onclick="loadDocs()">Refresh</button>
    </div>`;

  loadDocs();
}

async function doSearch() {
  const q = document.getElementById('searchQ').value.trim();
  if (!q) return;
  const k = document.getElementById('searchK').value;
  const full = document.getElementById('searchFull').checked;
  const el = document.getElementById('searchResults');
  el.innerHTML = '<span class="text-muted text-[0.8rem]">Searching…</span>';
  try {
    const data = await api('GET', `/spaces/${currentSpace}/search?q=${encodeURIComponent(q)}&k=${k}&full=${full}`);
    if (!data.results.length) { el.innerHTML = '<span class="text-muted text-[0.8rem]">No results.</span>'; return; }
    el.innerHTML = `<div class="flex flex-col gap-3">${data.results.map(r => `
      <div class="bg-bg border border-border rounded px-4 py-3">
        <div class="flex justify-between text-xs text-muted mb-1.5">
          <span class="${TAG}">${esc(r.metadata?.filename || r.metadata?.source || 'doc')}</span>
          <span class="text-accent2 font-semibold">score ${r.score}</span>
        </div>
        <div class="text-sm leading-relaxed">${esc(r.text)}</div>
        ${r.full_text ? `<div class="mt-2 pt-2 border-t border-border text-[0.8rem] text-muted whitespace-pre-wrap max-h-[200px] overflow-y-auto">${esc(r.full_text)}</div>` : ''}
      </div>`).join('')}</div>`;
  } catch (e) {
    el.innerHTML = `<span class="text-danger text-[0.8rem]">${esc(e.message)}</span>`;
  }
}

async function doIngest() {
  const text = document.getElementById('ingestText').value.trim();
  const source = document.getElementById('ingestSource').value.trim();
  if (!text) return;
  const fd = new FormData();
  fd.append('text', text);
  if (source) fd.append('source', source);
  await submitIngest(fd);
  document.getElementById('ingestText').value = '';
}

async function doUpload() {
  const file = document.getElementById('ingestFile').files[0];
  if (!file) return;
  const fd = new FormData();
  fd.append('file', file);
  const ext = file.name.split('.').pop().toLowerCase();
  const hints = { pdf: 'extracting PDF text', mp3: 'transcribing audio', wav: 'transcribing audio', ogg: 'transcribing audio', m4a: 'transcribing audio', flac: 'transcribing audio', webm: 'transcribing audio' };
  await submitIngest(fd, hints[ext] || null);
  document.getElementById('ingestFile').value = '';
}

async function submitIngest(fd, hint = null) {
  const status = document.getElementById('ingestStatus');
  const hintText = hint ? ` <span class="text-muted">(${hint} — this may take a moment)</span>` : '';
  status.innerHTML = `<span class="text-muted text-[0.8rem]">Ingesting…${hintText}</span>`;
  try {
    const r = await api('POST', `/spaces/${currentSpace}/documents`, fd);
    status.innerHTML = `<span class="${STATUS_OK}">Ingested — ${r.chunk_count} chunks · id: ${r.doc_id}</span>`;
    loadDocs();
  } catch (e) {
    status.innerHTML = `<span class="${STATUS_ERR}">${esc(e.message)}</span>`;
  }
}

async function loadDocs() {
  const el = document.getElementById('docsList');
  if (!el) return;
  try {
    const { documents } = await api('GET', `/spaces/${currentSpace}/documents`);
    if (!documents.length) { el.innerHTML = '<span class="text-muted text-[0.8rem]">No documents yet.</span>'; return; }
    const typeLabel = { pdf: 'PDF', image: 'IMG', audio: 'AUD' };
    el.innerHTML = `<div class="flex flex-col gap-1.5">${documents.map((d, i) => `
      <div class="flex justify-between items-center text-[0.8rem] py-1 ${i < documents.length - 1 ? 'border-b border-border' : ''}">
        <span class="font-mono text-accent cursor-pointer hover:underline" onclick="fetchDoc(${JSON.stringify(d.doc_id)})">${esc(d.doc_id.slice(0,12))}…</span>
        <span class="text-muted text-xs flex items-center gap-1.5">${typeLabel[d.doc_type] ? `<span class="${TAG}">${typeLabel[d.doc_type]}</span>` : ''}${esc(d.filename || d.source || '')}</span>
        <button class="${BTN_DANGER}" onclick="delDoc(${JSON.stringify(d.doc_id)})">delete</button>
      </div>`).join('')}</div>`;
  } catch (e) {
    el.innerHTML = `<span class="text-danger text-[0.8rem]">${esc(e.message)}</span>`;
  }
}

async function fetchDoc(id) {
  const doc = await api('GET', `/spaces/${currentSpace}/documents/${id}`);
  alert(`[${id}]\n\n${doc.text.slice(0, 1000)}${doc.text.length > 1000 ? '…' : ''}`);
}

async function delDoc(id) {
  if (!confirm(`Delete document ${id}?`)) return;
  await api('DELETE', `/spaces/${currentSpace}/documents/${id}`);
  loadDocs();
}

function esc(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

// ── Settings ──────────────────────────────────────────────────────────────

async function openSettings() {
  loadApiKeys().catch(() => {});
  if (authEnabled && !isApiKeyAuth) {
    document.getElementById('changePasswordSection').classList.remove('hidden');
    document.getElementById('changePasswordStatus').innerHTML = '';
    document.getElementById('currentPassword').value = '';
    document.getElementById('newPassword').value = '';
  }
  if (authEnabled && isAdmin) loadUsers().catch(() => {});
  let s;
  try {
    s = await api('GET', '/settings');
  } catch (e) {
    return; // 401 already redirected to login page
  }
  const urlField = document.getElementById('settingsOllamaUrl');
  const modelField = document.getElementById('settingsEmbedModel');

  urlField.value = s.ollama_url.value;
  urlField.readOnly = s.ollama_url.readonly;
  modelField.value = s.embed_model.value;
  modelField.readOnly = s.embed_model.readonly;

  document.getElementById('urlSourceBadge').textContent = s.ollama_url.source;
  document.getElementById('urlSourceBadge').className = sourceBadgeClass(s.ollama_url.source);
  document.getElementById('modelSourceBadge').textContent = s.embed_model.source;
  document.getElementById('modelSourceBadge').className = sourceBadgeClass(s.embed_model.source);

  const allReadonly = s.ollama_url.readonly && s.embed_model.readonly;
  document.getElementById('settingsNote').textContent = allReadonly
    ? 'All settings are locked by environment variables and cannot be changed here.'
    : s.ollama_url.readonly || s.embed_model.readonly
      ? 'Fields marked "env" are set by environment variables and cannot be changed here.'
      : 'These values are saved to disk and used when environment variables are not set.';

  document.getElementById('settingsStatus').innerHTML = '';
  document.getElementById('settingsOverlay').classList.replace('hidden', 'flex');
}

function closeSettings() {
  document.getElementById('settingsOverlay').classList.replace('flex', 'hidden');
}

function closeSettingsOnBackdrop(e) {
  if (e.target === document.getElementById('settingsOverlay')) closeSettings();
}

async function saveSettings() {
  const body = {
    ollama_url: document.getElementById('settingsOllamaUrl').value.trim() || null,
    embed_model: document.getElementById('settingsEmbedModel').value.trim() || null,
  };
  const statusEl = document.getElementById('settingsStatus');
  try {
    await api('POST', '/settings', body);
    statusEl.innerHTML = `<span class="${STATUS_OK}">Saved.</span>`;
  } catch (e) {
    statusEl.innerHTML = `<span class="${STATUS_ERR}">${esc(e.message)}</span>`;
  }
}

// ── Logs ──────────────────────────────────────────────────────────────────

let logsInterval = null;
const logsExpanded = new Set();

async function openLogs() {
  document.getElementById('logsOverlay').classList.replace('hidden', 'flex');
  await refreshLogs();
  logsInterval = setInterval(refreshLogs, 2000);
}

function closeLogs() {
  document.getElementById('logsOverlay').classList.replace('flex', 'hidden');
  clearInterval(logsInterval);
  logsInterval = null;
}

function closeLogsOnBackdrop(e) {
  if (e.target === document.getElementById('logsOverlay')) closeLogs();
}

async function refreshLogs() {
  try {
    const { logs } = await api('GET', '/logs');
    const tbody = document.getElementById('logsBody');
    if (!tbody) return;
    if (!logs.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="text-muted p-2">No requests yet.</td></tr>';
      return;
    }
    tbody.innerHTML = logs.map(l => {
      const cls = l.status >= 500 ? 'text-danger' : l.status >= 400 ? 'text-[#fbbf24]' : 'text-success';
      const hasDetail = !!l.detail;
      const open = logsExpanded.has(l.seq);
      const detailRow = hasDetail
        ? `<tr id="logd-${l.seq}" style="display:${open ? 'table-row' : 'none'}"><td colspan="5" class="text-danger text-[0.7rem] px-2 py-1 whitespace-pre-wrap break-all bg-[#1a0a0a] border-b border-[#2e1010]">${esc(String(l.detail))}</td></tr>`
        : '';
      const expandBtn = hasDetail
        ? `<span data-log-expand class="cursor-pointer text-muted text-[0.7rem] px-1 hover:text-danger">${open ? '▼' : '▶'}</span>`
        : '';
      return `<tr style="cursor:${hasDetail ? 'pointer' : 'default'}" onclick="${hasDetail ? `toggleLogDetail(${l.seq})` : ''}">
        <td class="text-muted px-2 py-1 border-b border-[#1e2030] whitespace-nowrap">${l.ts}</td>
        <td class="text-accent px-2 py-1 border-b border-[#1e2030] whitespace-nowrap">${l.method}</td>
        <td class="text-text max-w-[240px] overflow-hidden text-ellipsis px-2 py-1 border-b border-[#1e2030] whitespace-nowrap" title="${esc(l.path)}">${esc(l.path)}</td>
        <td class="${cls} px-2 py-1 border-b border-[#1e2030] whitespace-nowrap">${l.status}${expandBtn}</td>
        <td class="text-muted px-2 py-1 border-b border-[#1e2030] whitespace-nowrap">${l.ms}ms</td>
      </tr>${detailRow}`;
    }).join('');
  } catch (_) {}
}

function toggleLogDetail(seq) {
  if (logsExpanded.has(seq)) {
    logsExpanded.delete(seq);
  } else {
    logsExpanded.add(seq);
  }
  const row = document.getElementById(`logd-${seq}`);
  if (row) row.style.display = logsExpanded.has(seq) ? 'table-row' : 'none';
  const rows = document.querySelectorAll('#logsBody tr');
  rows.forEach(r => {
    if (r.onclick && r.onclick.toString().includes(`(${seq})`)) {
      const span = r.querySelector('[data-log-expand]');
      if (span) span.textContent = logsExpanded.has(seq) ? '▼' : '▶';
    }
  });
}

async function clearLogs() {
  await api('DELETE', '/logs');
  await refreshLogs();
}

// ── Init ──────────────────────────────────────────────────────────────────

document.getElementById('newSpaceName').addEventListener('keydown', e => {
  if (e.key === 'Enter') createSpace();
});
document.getElementById('newCollectionName').addEventListener('keydown', e => {
  if (e.key === 'Enter') createCollection();
});

async function init() {
  const ok = await checkAuth();
  if (!ok) return;
  loadSpaces();
  loadCollections();
}

init();
