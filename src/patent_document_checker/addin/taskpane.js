(() => {
  const $ = selector => document.querySelector(selector);
  const status = $('#status');
  const summary = $('#summary');
  const results = $('#results');

  const escapeHtml = value => String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');

  const apiUrlInput = $('#api-url');
  apiUrlInput.value = window.location.origin;

  const apiBase = () => apiUrlInput.value.replace(/\/$/, '');

  const setBusy = busy => {
    document.querySelectorAll('button').forEach(button => { button.disabled = busy; });
  };

  const setStatus = (message, isError = false) => {
    status.textContent = message;
    status.classList.toggle('error', isError);
  };

  const section = (title, body) => `<div class="section"><h2>${escapeHtml(title)}</h2>${body}</div>`;

  const formatClaimNumbers = numbers => {
    if (!numbers || !numbers.length) return '－';
    return numbers.map(number => `請求項${number}`).join('、');
  };

  const renderDiagnostics = diagnostics => {
    if (!diagnostics.length) return section('診断結果', '<div class="empty">No diagnostics.</div>');
    return section('診断結果', `<table><thead><tr><th>区分</th><th>内容</th></tr></thead><tbody>${diagnostics.map(item => `
      <tr>
        <td>${escapeHtml(item.severity_label || item.severity)}</td>
        <td>${escapeHtml(item.message)}<div class="meta">${escapeHtml(item.rule_label || item.rule_id)} / ${escapeHtml(item.location || '')}</div></td>
      </tr>`).join('')}</tbody></table>`);
  };

  const renderClaims = claims => {
    if (!claims.length) return section('請求項の関係', '<div class="empty">No claims.</div>');
    const incoming = new Map();
    claims.forEach(claim => (claim.referenced_claims || []).forEach(number => {
      const list = incoming.get(Number(number)) || [];
      list.push(Number(claim.number));
      incoming.set(Number(number), list);
    }));
    return section('請求項の関係', `<table><thead><tr><th>請求項</th><th>従属先</th><th>被従属</th><th>種別</th></tr></thead><tbody>${claims.map(claim => {
      const refs = claim.referenced_claims || [];
      const relation = refs.length ? (claim.is_multiple_dependent ? '複数従属項' : '従属項') : '独立項';
      const incomingClaims = [...new Set(incoming.get(Number(claim.number)) || [])].sort((a, b) => a - b);
      return `<tr><td>請求項${escapeHtml(claim.number)}</td><td>${escapeHtml(formatClaimNumbers(refs))}</td><td>${escapeHtml(formatClaimNumbers(incomingClaims))}</td><td>${escapeHtml(relation)}</td></tr>`;
    }).join('')}</tbody></table>`);
  };

  const renderReferenceSigns = entries => {
    const output = entries.map(entry => `${entry.sign}…${entry.term}`).join('，');
    const rows = entries.map(entry => `<tr><td>${escapeHtml(entry.sign)}</td><td>${escapeHtml(entry.term)}</td><td>${escapeHtml(entry.source)}</td></tr>`).join('');
    return section('符号の説明用一覧', `
      <div class="reference-output">${escapeHtml(output || 'No signed terms.')}</div>
      ${entries.length ? `<table><thead><tr><th>符号</th><th>語句</th><th>出現場所</th></tr></thead><tbody>${rows}</tbody></table>` : ''}`);
  };

  const renderTermOccurrences = occurrences => {
    const rows = Object.entries(occurrences || {}).sort(([a], [b]) => a.localeCompare(b, 'ja'));
    if (!rows.length) return section('語句出現表', '<div class="empty">No term occurrences.</div>');
    return section('語句出現表', `<table><thead><tr><th>語句</th><th>出現場所</th></tr></thead><tbody>${rows.map(([term, locations]) => `<tr><td>${escapeHtml(term)}</td><td>${escapeHtml((locations || []).join('、'))}</td></tr>`).join('')}</tbody></table>`);
  };

  const renderUnits = units => {
    if (!units.length) return section('単位チェック', '<div class="empty">No unit expressions.</div>');
    return section('単位チェック', `<table><thead><tr><th>マッチ</th><th>単位</th><th>内容</th></tr></thead><tbody>${units.map(item => `<tr><td>${escapeHtml(item.matched)}</td><td>${escapeHtml(item.unit)}</td><td>${escapeHtml(item.message)}</td></tr>`).join('')}</tbody></table>`);
  };

  const render = data => {
    const counts = data.summary || { error: 0, warning: 0, info: 0 };
    summary.innerHTML = `
      <span class="pill error">Error ${counts.error ?? 0}</span>
      <span class="pill warning">Warning ${counts.warning ?? 0}</span>
      <span class="pill info">Info ${counts.info ?? 0}</span>`;
    results.className = '';
    results.innerHTML = [
      renderDiagnostics(data.diagnostic_views || []),
      renderClaims(data.claims || []),
      renderReferenceSigns(data.reference_sign_entries || []),
      renderTermOccurrences(data.term_occurrences || {}),
      renderUnits(data.unit_checks || []),
    ].join('');
  };

  const checkApi = async () => {
    setBusy(true);
    try {
      const response = await fetch(`${apiBase()}/health`);
      const data = await response.json();
      if (!response.ok || data.status !== 'ok') throw new Error('API status is not ok.');
      setStatus('API ready');
    } catch (error) {
      setStatus(error.message || String(error), true);
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
    try {
      const text = await getDocumentText();
      if (!text.trim()) throw new Error('文書本文が空です。');
      setStatus('解析中...');
      const response = await fetch(`${apiBase()}/api/check-text`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, source: 'word-addin' }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || response.statusText);
      render(data);
      setStatus('解析が完了しました。');
    } catch (error) {
      setStatus(error.message || String(error), true);
    } finally {
      setBusy(false);
    }
  };

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
