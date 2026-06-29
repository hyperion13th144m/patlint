(() => {
  const $ = selector => document.querySelector(selector);
  const status = $('#status');
  const summary = $('#summary');
  const aiPanel = $('#ai-panel');
  const aiStatus = $('#ai-status');
  const tokenLog = $('#token-log');

  const escapeHtml = value => String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');

  const apiUrlInput = $('#api-url');
  apiUrlInput.value = window.location.origin;
  const apiBase = () => apiUrlInput.value.replace(/\/$/, '');

  const state = { documentId: null, proofreadResults: [], proofreadDone: false, lastDiagnostics: [] };

  // -----------------------------------------------------------------------
  // Busy / status helpers
  // -----------------------------------------------------------------------

  const setBusy = busy => {
    document.querySelectorAll('main button:not(#ai-submit):not(#ai-cancel):not(#ai-clear)').forEach(b => { b.disabled = busy; });
  };

  const setStatus = (message, isError = false) => {
    status.textContent = message;
    status.classList.toggle('error', isError);
  };

  let _aiAbortController = null;

  const setAiBusy = busy => {
    $('#ai-submit').disabled = busy;
    $('#ai-cancel').classList.toggle('hidden', !busy);
  };

  // -----------------------------------------------------------------------
  // Result tabs
  // -----------------------------------------------------------------------

  const switchResultTab = panelId => {
    document.querySelectorAll('.result-tab').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.panel === panelId);
    });
    document.querySelectorAll('.tab-panel').forEach(panel => {
      panel.classList.toggle('active', panel.id === panelId);
    });
  };

  document.querySelectorAll('.result-tab').forEach(btn => {
    btn.addEventListener('click', () => switchResultTab(btn.dataset.panel));
  });

  // -----------------------------------------------------------------------
  // Render helpers
  // -----------------------------------------------------------------------

  const section = (title, body) => `<div class="section"><h2>${escapeHtml(title)}</h2>${body}</div>`;

  const SEVERITY_ORDER = { error: 0, warning: 1, info: 2 };
  const SEVERITY_DOT = { error: '●', warning: '▲', info: '◆' };

  const extractHeader = text => {
    const m = String(text).match(/^(【[^】]*】)/);
    return m ? m[1] : null;
  };

  const isAiRule = ruleId => String(ruleId).startsWith('AI_');

  // アコーディオン開閉（グローバル関数）
  window.toggleIssueDetail = summaryEl => {
    const detail = summaryEl.parentElement.querySelector('.issue-detail');
    const toggle = summaryEl.querySelector('.issue-toggle');
    if (!detail) return;
    const open = detail.classList.toggle('open');
    if (toggle) toggle.textContent = open ? '▼ 詳細' : '▶ 詳細';
  };

  // 重要度フィルター（グローバル関数）
  window.toggleSevFilter = btn => {
    const sev = btn.dataset.sev;
    const activeClass = `active-${sev}`;
    const isActive = btn.classList.toggle(activeClass);
    const tableId = btn.closest('.severity-filter').dataset.table;
    const table = document.getElementById(tableId);
    if (!table) return;
    table.querySelectorAll(`.issue-item[data-severity="${sev}"]`).forEach(item => {
      item.toggleAttribute('data-hidden', !isActive);
    });
    table.querySelectorAll('tbody tr').forEach(row => {
      const items = row.querySelectorAll('.issue-item');
      const allHidden = [...items].every(i => i.hasAttribute('data-hidden'));
      row.style.display = allHidden ? 'none' : '';
    });
  };

  const renderGroupedDiagnostics = (title, diagnostics, blocks) => {
    if (!diagnostics.length) return `<div class="empty">指摘事項はありません。</div>`;

    const blockMap = new Map(blocks.map(b => [b.index, b]));
    const findBlockBySearchText = searchText => {
      if (!searchText) return null;
      const header = extractHeader(searchText) || searchText;
      for (const b of blocks) {
        if (b.text.startsWith(header)) return b;
      }
      return null;
    };

    const withBlock = diagnostics.map(d => {
      const loc = d.location_data || {};
      let block = null;
      if (loc.block_index != null) block = blockMap.get(loc.block_index) || null;
      if (!block && loc.search_text) block = findBlockBySearchText(loc.search_text);
      return { d, block };
    });

    const groups = new Map();
    for (const { d, block } of withBlock) {
      const key = block != null ? block.index : '__unknown__';
      if (!groups.has(key)) groups.set(key, { block, items: [] });
      groups.get(key).items.push(d);
    }

    const sorted = [...groups.entries()].sort(([ka], [kb]) => {
      if (ka === '__unknown__') return 1;
      if (kb === '__unknown__') return -1;
      return Number(ka) - Number(kb);
    });

    const rows = sorted.filter(([, { block }]) => {
      if (!block) return true;
      return !!extractHeader(block.text);
    });

    if (!rows.length) return `<div class="empty">指摘事項はありません。</div>`;

    const rowsHtml = rows.map(([, { block, items }]) => {
      let header;
      if (block) {
        header = extractHeader(block.text) || '（位置不明）';
      } else if (items[0]?.location_data?.search_text) {
        header = items[0].location_data.search_text;
      } else {
        header = '（位置不明）';
      }

      const sortedItems = [...items].sort((a, b) =>
        (SEVERITY_ORDER[a.severity] ?? 9) - (SEVERITY_ORDER[b.severity] ?? 9)
      );

      const issuesHtml = sortedItems.map((d, localIdx) => {
        const hasDetail = d.reason || d.suggestion || d.original_text;
        const hasLocation = d.location_data && (d.location_data.search_text != null || d.location_data.block_index != null);
        const globalIdx = state.lastDiagnostics.indexOf(d);
        const jumpBtn = hasLocation && globalIdx >= 0
          ? `<button class="secondary jump-btn" data-diag-idx="${globalIdx}">移動</button>`
          : '';
        const detailHtml = hasDetail ? `
          <div class="issue-detail">
            ${d.original_text ? `<div class="issue-detail-row"><span class="issue-detail-key">原文</span>${escapeHtml(d.original_text)}</div>` : ''}
            ${d.reason ? `<div class="issue-detail-row"><span class="issue-detail-key">根拠</span>${escapeHtml(d.reason)}</div>` : ''}
            ${d.suggestion ? `<div class="issue-detail-row"><span class="issue-detail-key">修正案</span>${escapeHtml(d.suggestion)}</div>` : ''}
          </div>` : '';
        return `
          <div class="issue-item" data-severity="${escapeHtml(d.severity)}">
            <span class="issue-dot ${escapeHtml(d.severity)}">${SEVERITY_DOT[d.severity] || '・'}</span>
            <div class="issue-body">
              <div class="issue-label">${isAiRule(d.rule_id) ? '<span class="ai-badge">AI</span>' : ''}${escapeHtml(d.rule_label)}</div>
              <div class="issue-summary"${hasDetail ? ' onclick="toggleIssueDetail(this)"' : ''}>
                <span class="issue-message">${escapeHtml(d.message)}</span>
                ${hasDetail ? '<span class="issue-toggle">▶ 詳細</span>' : ''}
              </div>
              ${detailHtml}
              ${jumpBtn}
            </div>
          </div>`;
      }).join('');

      return `<tr><td class="location-cell">${escapeHtml(header)}</td><td class="issues-cell">${issuesHtml}</td></tr>`;
    }).join('');

    const sevCount = { error: 0, warning: 0, info: 0 };
    for (const [, { items }] of rows) {
      for (const d of items) sevCount[d.severity] = (sevCount[d.severity] || 0) + 1;
    }
    const tableId = `gt-${Math.random().toString(36).slice(2)}`;
    const filterBar = `
      <div class="severity-filter" data-table="${tableId}">
        <span>表示：</span>
        ${sevCount.error > 0 ? `<button class="sev-btn active-error" data-sev="error" onclick="toggleSevFilter(this)">● Error ${sevCount.error}</button>` : ''}
        ${sevCount.warning > 0 ? `<button class="sev-btn active-warning" data-sev="warning" onclick="toggleSevFilter(this)">▲ Warning ${sevCount.warning}</button>` : ''}
        ${sevCount.info > 0 ? `<button class="sev-btn active-info" data-sev="info" onclick="toggleSevFilter(this)">◆ Info ${sevCount.info}</button>` : ''}
      </div>`;

    return `
      ${filterBar}
      <table class="grouped-table" id="${tableId}">
        <thead><tr><th style="width:80px;">箇所</th><th>指摘事項</th></tr></thead>
        <tbody>${rowsHtml}</tbody>
      </table>`;
  };

  const formatClaimNumbers = numbers => {
    if (!numbers || !numbers.length) return '－';
    return numbers.map(n => `請求項${n}`).join('、');
  };

  const renderClaims = claims => {
    if (!claims.length) return section('請求項の関係', '<div class="empty">請求項データがありません。</div>');
    const incoming = new Map(claims.map(c => [Number(c.number), []]));
    claims.forEach(c => {
      (c.referenced_claims || []).forEach(n => {
        const key = Number(n);
        if (!incoming.has(key)) incoming.set(key, []);
        incoming.get(key).push(Number(c.number));
      });
    });
    const rows = [...claims].sort((a, b) => Number(a.number) - Number(b.number));
    return section('請求項の関係', `
      <table>
        <thead><tr><th>請求項</th><th>従属先</th><th>被従属</th><th>種別</th><th>状態</th></tr></thead>
        <tbody>${rows.map(claim => {
          const refs = (claim.referenced_claims || []).map(Number);
          const relation = !refs.length ? '独立項' : new Set(refs).size > 1 ? '複数従属項' : '従属項';
          const states = [];
          if (claim.is_multi_multi) states.push('マルチマルチ');
          if (claim.references_multi_multi) states.push('マルチマルチを引用');
          if (claim.references_multiple_dependent) states.push('複数従属項を引用');
          const incomingClaims = [...new Set(incoming.get(Number(claim.number)) || [])].sort((a, b) => a - b);
          return `<tr>
            <td>請求項${escapeHtml(claim.number)}</td>
            <td>${escapeHtml(formatClaimNumbers(refs))}</td>
            <td>${escapeHtml(formatClaimNumbers(incomingClaims))}</td>
            <td>${escapeHtml(relation)}</td>
            <td>${escapeHtml(states.length ? states.join('、') : '－')}</td>
          </tr>`;
        }).join('')}</tbody>
      </table>`);
  };

  // 符号の説明（Web UIと同じソートロジック）
  const normalizeSign = value => String(value)
    .replace(/[Ａ-Ｚａ-ｚ０-９]/g, ch => String.fromCharCode(ch.charCodeAt(0) - 0xFEE0))
    .replace(/[－ー―‐]/g, '-')
    .replace(/['＇]/g, "'")
    .replace(/[　\s]+/g, '')
    .toUpperCase();
  const toFullWidth = value => String(value)
    .replace(/[A-Za-z0-9]/g, ch => String.fromCharCode(ch.charCodeAt(0) + 0xFEE0))
    .replace(/-/g, '－')
    .replace(/'/g, '‘');
  const toHalfWidth = value => normalizeSign(value).replace(/'/g, "'");
  const signRank = sign => {
    const normalized = normalizeSign(sign);
    const match = normalized.match(/^([A-Z]+)?(?:-)?(\d+)?(.*)$/);
    if (!match) return [3, normalized];
    const letters = match[1] || '';
    const number = match[2] ? Number(match[2]) : null;
    const rest = match[3] || '';
    if (letters && number === null) return [0, letters, rest];
    if (letters && number !== null) return [0, letters, 0, number, rest];
    if (number !== null) return [1, number, /^[A-ZＡ-Ｚａ-ｚぁ-んァ-ヶ]/.test(rest) ? 1 : rest.startsWith('-') ? 2 : 3, rest];
    return [2, normalized];
  };
  const compareRank = (left, right) => {
    const max = Math.max(left.length, right.length);
    for (let i = 0; i < max; i++) {
      if (left[i] === right[i]) continue;
      if (left[i] === undefined) return -1;
      if (right[i] === undefined) return 1;
      if (typeof left[i] === 'number' && typeof right[i] === 'number') return left[i] - right[i];
      return String(left[i]).localeCompare(String(right[i]), 'ja', { numeric: true });
    }
    return 0;
  };

  const renderReferenceSigns = entries => {
    const rows = entries.map(e => `<tr><td>${escapeHtml(e.sign)}</td><td>${escapeHtml(e.term)}</td><td>${escapeHtml(e.source)}</td></tr>`).join('');
    return section('符号の説明用一覧', `
      <div class="reference-controls">
        <label>連結記号
          <select id="reference-joiner">
            <option value="…" selected>三点リーダ</option>
            <option value="　">空白</option>
          </select>
        </label>
        <label>区切り文字
          <select id="reference-separator">
            <option value="、">読点（、）</option>
            <option value="，" selected>カンマ（，）</option>
            <option value="__newline__">改行</option>
          </select>
        </label>
        <label>符号
          <select id="reference-width">
            <option value="full" selected>全角</option>
            <option value="half">半角</option>
          </select>
        </label>
        <label class="check"><input type="checkbox" id="reference-sort" checked> 昇順にソート</label>
      </div>
      <div class="reference-output" id="reference-output"></div>
      <h2 style="font-size:13px;margin:8px 0 5px;">抽出元</h2>
      ${entries.length ? `
        <table>
          <thead><tr><th>符号</th><th>語句</th><th>出現場所</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      ` : '<div class="empty">No signed terms.</div>'}
    `);
  };

  const attachReferenceControls = entries => {
    const output = $('#reference-output');
    if (!output) return;
    const renderReferenceOutput = () => {
      const joiner = $('#reference-joiner').value;
      const separator = $('#reference-separator').value === '__newline__' ? '\n' : $('#reference-separator').value;
      const width = $('#reference-width').value;
      const items = entries.map((e, i) => ({ ...e, index: i }));
      if ($('#reference-sort').checked) {
        items.sort((a, b) => compareRank(signRank(a.sign), signRank(b.sign)) || a.index - b.index);
      }
      output.textContent = items.map(e => {
        const sign = width === 'full' ? toFullWidth(e.sign) : toHalfWidth(e.sign);
        return `${sign}${joiner}${e.term}`;
      }).join(separator);
    };
    document.querySelectorAll('#reference-joiner, #reference-separator, #reference-width, #reference-sort')
      .forEach(el => el.addEventListener('change', renderReferenceOutput));
    renderReferenceOutput();
  };

  const renderTermOccurrences = occurrences => {
    const rows = Object.entries(occurrences || {}).sort(([a], [b]) => a.localeCompare(b, 'ja'));
    if (!rows.length) return section('語句出現表', '<div class="empty">No term occurrences.</div>');
    return section('語句出現表', `
      <table>
        <thead><tr><th>語句</th><th>出現場所</th></tr></thead>
        <tbody>${rows.map(([term, locs]) => `<tr><td>${escapeHtml(term)}</td><td>${escapeHtml((locs || []).join('、'))}</td></tr>`).join('')}</tbody>
      </table>`);
  };

  const renderUnits = units => {
    if (!units.length) return section('単位チェック', '<div class="empty">No unit expressions.</div>');
    return section('単位チェック', `
      <table>
        <thead><tr><th>行</th><th>桁</th><th>マッチ</th><th>単位</th><th>内容</th></tr></thead>
        <tbody>${units.map(item => `
          <tr>
            <td>${escapeHtml(item.line)}</td>
            <td>${escapeHtml(item.col)}</td>
            <td>${escapeHtml(item.matched)}</td>
            <td>${escapeHtml(item.unit)}</td>
            <td>${escapeHtml(item.message)}</td>
          </tr>`).join('')}</tbody>
      </table>`);
  };

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------

  const render = data => {
    state.lastDiagnostics = data.diagnostic_views || [];
    const counts = data.summary || { error: 0, warning: 0, info: 0 };
    summary.innerHTML = `
      <span class="pill error">Error ${counts.error ?? 0}</span>
      <span class="pill warning">Warning ${counts.warning ?? 0}</span>
      <span class="pill info">Info ${counts.info ?? 0}</span>`;

    $('#results').classList.add('hidden');
    $('#result-tabs').classList.remove('hidden');

    const allViews = data.diagnostic_views || [];
    const blocks = data.blocks || [];
    const ruleViews = allViews.filter(d => !isAiRule(d.rule_id));

    $('#panel-diagnostics').innerHTML = renderGroupedDiagnostics('診断結果', ruleViews, blocks);
    $('#panel-claims').innerHTML = renderClaims(data.claims || []);
    $('#panel-reference').innerHTML = renderReferenceSigns(data.reference_sign_entries || []);
    $('#panel-terms').innerHTML = [
      renderTermOccurrences(data.term_occurrences || {}),
      renderUnits(data.unit_checks || []),
    ].join('');

    attachReferenceControls(data.reference_sign_entries || []);
    switchResultTab('panel-diagnostics');
  };

  // -----------------------------------------------------------------------
  // Jump to location (Word-specific)
  // -----------------------------------------------------------------------

  const jumpToLocation = async location => {
    try {
      await Word.run(async context => {
        if (location.search_text) {
          const found = context.document.body.search(location.search_text, { matchCase: false, matchWholeWord: false });
          found.load('items');
          await context.sync();
          if (found.items.length > 0) {
            found.items[0].select('Select');
            await context.sync();
            return;
          }
        }
        if (location.block_index != null) {
          const paragraphs = context.document.body.paragraphs;
          paragraphs.load('items');
          await context.sync();
          const target = paragraphs.items[location.block_index];
          if (target) { target.select('Select'); await context.sync(); }
        }
      });
    } catch (err) {
      setStatus('移動に失敗しました: ' + (err.message || String(err)), true);
    }
  };

  document.addEventListener('click', e => {
    const btn = e.target.closest('.jump-btn');
    if (!btn) return;
    const idx = Number(btn.dataset.diagIdx);
    const item = state.lastDiagnostics[idx];
    if (item?.location_data) jumpToLocation(item.location_data);
  });

  // -----------------------------------------------------------------------
  // API check / document check
  // -----------------------------------------------------------------------

  const checkApi = async () => {
    setBusy(true);
    try {
      const response = await fetch(`${apiBase()}/health`);
      const data = await response.json();
      if (!response.ok || data.status !== 'ok') throw new Error('API status is not ok.');
      setStatus('API ready');
      $('#health').textContent = 'API ready';
    } catch (error) {
      setStatus(error.message || String(error), true);
      $('#health').textContent = 'API unavailable';
    } finally {
      setBusy(false);
    }
  };

  const getDocumentText = async () => Word.run(async context => {
    const body = context.document.body;
    body.load('text');
    await context.sync();
    return body.text || '';
  });

  const checkDocument = async () => {
    setBusy(true);
    setStatus('文書を読み取っています...');
    aiPanel.classList.add('hidden');
    tokenLog.innerHTML = '';
    state.documentId = null;
    state.proofreadResults = [];
    state.proofreadDone = false;
    $('#results').classList.remove('hidden');
    $('#results').className = 'empty';
    $('#results').textContent = '解析中...';
    $('#result-tabs').classList.add('hidden');
    ['panel-diagnostics', 'panel-claims', 'panel-reference', 'panel-terms', 'panel-ai'].forEach(id => {
      const el = document.getElementById(id);
      if (el) { el.innerHTML = ''; el.classList.remove('active'); }
    });
    document.getElementById('panel-diagnostics')?.classList.add('active');
    const badge = $('#ai-tab')?.querySelector('.result-tab-badge');
    if (badge) badge.remove();
    const aiPill = summary.querySelector('.pill.ai');
    if (aiPill) aiPill.remove();

    try {
      const text = await getDocumentText();
      if (!text.trim()) throw new Error('文書本文が空です。');
      setStatus('解析中...');
      const response = await fetch(`${apiBase()}/api/documents/upload-text`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, source: 'word-addin' }),
      });
      const responseText = await response.text();
      let data = {};
      if (responseText) data = JSON.parse(responseText);
      if (!response.ok) throw new Error(data.detail || response.statusText);
      render(data);
      if (data.document_id) {
        state.documentId = data.document_id;
        aiPanel.classList.remove('hidden');
        updateAiSubmitState();
      }
      setStatus('解析が完了しました。');
    } catch (error) {
      setStatus(error.message || String(error), true);
    } finally {
      setBusy(false);
    }
  };

  // -----------------------------------------------------------------------
  // AI proofreading
  // -----------------------------------------------------------------------

  const updateAiSubmitState = () => {
    $('#ai-submit').disabled = state.proofreadDone;
    $('#ai-clear').classList.toggle('hidden', !state.proofreadDone);
    if (state.proofreadDone) {
      aiStatus.textContent = '校正済みです。クリアして再実行できます。';
    } else if (!aiStatus.textContent.includes('実行中') && !aiStatus.textContent.includes('エラー')) {
      aiStatus.textContent = '';
    }
  };

  $('#ai-provider').addEventListener('change', () => {
    const provider = $('#ai-provider').value;
    $('#ollama-model-row').classList.toggle('hidden', provider !== 'ollama');
    updateAiSubmitState();
  });

  $('#ai-cancel').addEventListener('click', () => {
    if (_aiAbortController) { _aiAbortController.abort(); _aiAbortController = null; }
  });

  $('#ai-clear').addEventListener('click', () => {
    state.proofreadResults = [];
    state.proofreadDone = false;
    document.getElementById('proofread-section')?.remove();
    $('#panel-ai').innerHTML = '';
    summary.querySelector('.pill.ai')?.remove();
    $('#ai-tab')?.querySelector('.result-tab-badge')?.remove();
    aiStatus.textContent = '';
    tokenLog.innerHTML = '';
    updateAiSubmitState();
  });

  // Character-level diff (LCS)
  const diffChars = (a, b) => {
    const m = a.length, n = b.length;
    if (m * n > 400000) return [{ text: a, type: 'del' }, { text: b, type: 'ins' }];
    const dp = Array.from({ length: m + 1 }, () => new Uint16Array(n + 1));
    for (let i = m - 1; i >= 0; i--)
      for (let j = n - 1; j >= 0; j--)
        dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    const ops = [];
    let i = 0, j = 0;
    while (i < m || j < n) {
      if (i < m && j < n && a[i] === b[j]) { ops.push({ ch: a[i], type: 'eq' }); i++; j++; }
      else if (j < n && (i >= m || dp[i][j + 1] >= dp[i + 1][j])) { ops.push({ ch: b[j], type: 'ins' }); j++; }
      else { ops.push({ ch: a[i], type: 'del' }); i++; }
    }
    const runs = [];
    for (const op of ops) {
      if (runs.length && runs[runs.length - 1].type === op.type) runs[runs.length - 1].text += op.ch;
      else runs.push({ text: op.ch, type: op.type });
    }
    return runs;
  };

  const renderDiffHtml = (original, corrected) => {
    const runs = diffChars(original, corrected);
    let beforeHtml = '', afterHtml = '';
    for (const run of runs) {
      const escaped = escapeHtml(run.text);
      if (run.type === 'eq') { beforeHtml += escaped; afterHtml += escaped; }
      else if (run.type === 'del') beforeHtml += `<span class="diff-del">${escaped}</span>`;
      else afterHtml += `<span class="diff-ins">${escaped}</span>`;
    }
    return { beforeHtml, afterHtml };
  };

  const ensureProofreadSection = () => {
    if (document.getElementById('proofread-section')) return;
    const panelAi = $('#panel-ai');
    const sectionEl = document.createElement('div');
    sectionEl.id = 'proofread-section';
    sectionEl.className = 'section';
    sectionEl.innerHTML = `
      <h2 id="proofread-title">AI文書校正結果（0件）</h2>
      <table style="table-layout:fixed;">
        <thead><tr><th style="width:60px;">箇所</th><th>校正前</th><th>校正後</th></tr></thead>
        <tbody id="proofread-tbody"></tbody>
      </table>`;
    panelAi.innerHTML = '';
    panelAi.appendChild(sectionEl);
    switchResultTab('panel-ai');
  };

  const appendProofreadRow = item => {
    const tbody = document.getElementById('proofread-tbody');
    if (!tbody) return;
    let beforeHtml = '', afterHtml = '';
    if (item.has_correction && item.corrected_text) {
      ({ beforeHtml, afterHtml } = renderDiffHtml(item.original_text, item.corrected_text));
    }
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td style="width:60px;font-weight:600;font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:11px;vertical-align:top;">${escapeHtml(item.label)}</td>
      <td style="vertical-align:top;"><div class="proofread-before">${beforeHtml}</div></td>
      <td style="vertical-align:top;"><div class="proofread-after">${afterHtml}</div></td>`;
    tbody.appendChild(tr);
  };

  const updateProofreadSummary = () => {
    const titleEl = document.getElementById('proofread-title');
    if (!titleEl) return;
    const count = state.proofreadResults.filter(r => r._displayed).length;
    titleEl.textContent = `AI文書校正結果（${count}件）`;
    const pill = summary.querySelector('.pill.ai');
    if (pill) {
      pill.textContent = `AI校正 ${count}件`;
    } else if (count > 0) {
      const newPill = document.createElement('span');
      newPill.className = 'pill ai';
      newPill.textContent = `AI校正 ${count}件`;
      summary.appendChild(newPill);
    }
    const aiTabBtn = $('#ai-tab');
    if (aiTabBtn) {
      let badge = aiTabBtn.querySelector('.result-tab-badge');
      if (count > 0) {
        if (!badge) { badge = document.createElement('span'); badge.className = 'result-tab-badge'; aiTabBtn.appendChild(badge); }
        badge.textContent = count;
      } else if (badge) {
        badge.remove();
      }
    }
  };

  const consumeSse = async (response, onEvent, signal) => {
    const reader = response.body.getReader();
    if (signal) signal.addEventListener('abort', () => reader.cancel());
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const chunks = buffer.split('\n\n');
      buffer = chunks.pop();
      for (const chunk of chunks) {
        if (!chunk.trim()) continue;
        let eventName = 'message';
        let dataStr = '';
        for (const line of chunk.split('\n')) {
          if (line.startsWith('event:')) eventName = line.slice(6).trim();
          else if (line.startsWith('data:')) dataStr = line.slice(5).trim();
        }
        if (dataStr) {
          try { onEvent(eventName, JSON.parse(dataStr)); } catch { /* ignore */ }
        }
      }
    }
  };

  $('#ai-submit').addEventListener('click', async () => {
    if (!state.documentId) { aiStatus.textContent = '先に文書をチェックしてください。'; return; }

    const provider = $('#ai-provider').value;
    const anonymize = $('#ai-anonymize').checked;
    const model = provider === 'ollama' ? ($('#ai-ollama-model').value.trim() || null) : null;
    const endpoint = `${apiBase()}/api/documents/${state.documentId}/proofread`;

    _aiAbortController = new AbortController();
    const signal = _aiAbortController.signal;

    setAiBusy(true);
    aiStatus.textContent = 'AI文書校正実行中...';
    state.proofreadResults = [];
    tokenLog.innerHTML = '';

    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, model, anonymize }),
        signal,
      });
      if (!response.ok) {
        const text = await response.text();
        let detail = response.statusText;
        try { detail = JSON.parse(text).detail || detail; } catch { /* ignore */ }
        throw new Error(detail);
      }

      let totalBlocks = 0;
      let processed = 0;
      ensureProofreadSection();

      await consumeSse(response, (eventName, data) => {
        if (eventName === 'start') {
          totalBlocks = data.total || 0;
        } else if (eventName === 'result') {
          processed++;
          const item = {
            label: data.label,
            has_correction: data.has_correction,
            original_text: data.original_text,
            corrected_text: data.corrected_text || null,
          };
          state.proofreadResults.push(item);
          const isRealCorrection = item.has_correction && item.corrected_text && item.corrected_text !== item.original_text;
          if (isRealCorrection) { item._displayed = true; appendProofreadRow(item); }
          updateProofreadSummary();
          const prog = totalBlocks > 0 ? ` (${processed}/${totalBlocks})` : '';
          const correctedSoFar = state.proofreadResults.filter(r => r._displayed).length;
          aiStatus.textContent = `校正中${prog}… 修正あり ${correctedSoFar} 件`;

          const u = data.token_usage;
          if (u) {
            const now = new Date().toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
            const entry = document.createElement('div');
            entry.className = 'token-entry';
            entry.innerHTML = `<div class="token-label">${escapeHtml(now)} ${escapeHtml(data.label)}</div>`
              + `入力 ${u.input_tokens.toLocaleString()} / 出力 ${u.output_tokens.toLocaleString()} / 合計 ${u.total_tokens.toLocaleString()} トークン`;
            tokenLog.appendChild(entry);
          }
        } else if (eventName === 'done') {
          const correctionCount = state.proofreadResults.filter(r => r._displayed).length;
          state.proofreadDone = true;
          updateAiSubmitState();
          aiStatus.textContent = `AI文書校正完了（修正あり ${correctionCount} 件）`;

          const u = data.total_token_usage;
          if (u) {
            const now = new Date().toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
            const entry = document.createElement('div');
            entry.className = 'token-entry';
            entry.style.fontWeight = '600';
            entry.innerHTML = `<div class="token-label">${escapeHtml(now)} 合計</div>`
              + `入力 ${u.input_tokens.toLocaleString()} / 出力 ${u.output_tokens.toLocaleString()} / 合計 ${u.total_tokens.toLocaleString()} トークン`;
            tokenLog.appendChild(entry);
          }
        } else if (eventName === 'error') {
          aiStatus.textContent = `エラー: ${data.message || 'AI校正エラー'}`;
        }
      }, signal);
    } catch (error) {
      if (error.name === 'AbortError') {
        aiStatus.textContent = 'キャンセルしました。';
      } else {
        aiStatus.textContent = `エラー: ${error.message || String(error)}`;
      }
    } finally {
      _aiAbortController = null;
      setAiBusy(false);
      updateAiSubmitState();
    }
  });

  // -----------------------------------------------------------------------
  // Office.onReady
  // -----------------------------------------------------------------------

  Office.onReady(info => {
    if (info.host === Office.HostType.Word) {
      setStatus('Word 文書をチェックできます。');
    } else {
      setStatus('このアドインは Word で使用してください。', true);
    }
    $('#check-api').addEventListener('click', checkApi);
    $('#check-document').addEventListener('click', checkDocument);
  });
})();
