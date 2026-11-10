/* 첨부 컴포넌트 (ES5, 라이브러리 의존 없음).
 * [data-attach] 를 자동 초기화한다. 동적으로 추가한 요소는 Attach.init(el).
 * 선택한 파일은 <input type=file>.files 에 동기화되므로 일반 form submit 으로 전송된다. */
(function () {
  'use strict';

  function fmt(n) {
    var u = ['B', 'KB', 'MB', 'GB'], i = 0;
    while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
    return (i === 0 ? n : n.toFixed(1)) + u[i];
  }
  function csv(v) { return v ? v.split(',').filter(Boolean) : []; }
  function num(v) { return v ? parseInt(v, 10) : null; }
  function exts(name) { return name.toLowerCase().split('.').slice(1).filter(Boolean); }
  function make(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) { e.className = cls; }
    if (text !== undefined) { e.textContent = text; }
    return e;
  }
  function sum(files) {
    return files.reduce(function (s, f) { return s + f.size; }, 0);
  }

  function init(root) {
    if (root.__attach) { return root.__attach; }
    var at = function (k) { return root.getAttribute('data-' + k); };
    var cfg = { drop: at('ui') === 'drop', maxFiles: num(at('max-files')), maxFileSize: num(at('max-file-size')),
                maxTotal: num(at('max-total-size')), allow: csv(at('allow')), deny: csv(at('deny')) };
    var input = root.querySelector('.attach-input');
    var errBox = root.querySelector('.attach-errors');
    var list = root.querySelector('.attach-list');
    var trigger = root.querySelector('.attach-drop') || root.querySelector('.attach-btn');
    var files = [];

    // 삭제 표시가 없는 기존 파일의 개수/용량
    function kept() {
      var n = 0, size = 0;
      Array.prototype.forEach.call(list.querySelectorAll('.attach-item:not(.attach-new):not(.attach-deleted)'), function (li) {
        n++; size += parseInt(li.getAttribute('data-size'), 10) || 0;
      });
      return { n: n, size: size };
    }

    function sync() {
      var dt = new DataTransfer();
      files.forEach(function (f) { dt.items.add(f); });
      input.files = dt.files;
    }

    function showErrors(errs) {
      errBox.innerHTML = '';
      errs.forEach(function (m) { errBox.appendChild(make('div', '', m)); });
      errBox.classList.toggle('d-none', errs.length === 0);
    }

    function render() {
      Array.prototype.forEach.call(list.querySelectorAll('.attach-new'), function (li) { list.removeChild(li); });
      files.forEach(function (f, idx) {
        var li = make('li', 'list-group-item d-flex align-items-center py-2 attach-item attach-new');
        if (f.type.indexOf('image/') === 0) {
          var img = make('img', 'attach-thumb');
          img.src = URL.createObjectURL(f);
          img.onload = function () { URL.revokeObjectURL(img.src); };
          li.appendChild(img);
        } else {
          li.appendChild(make('span', 'attach-badge mr-3', (exts(f.name).pop() || '').slice(0, 4)));
        }
        var del = make('button', 'btn btn-sm btn-outline-danger', '삭제');
        del.type = 'button';
        del.addEventListener('click', function () { files.splice(idx, 1); sync(); render(); showErrors([]); });
        li.appendChild(make('span', 'attach-name flex-grow-1', f.name));
        li.appendChild(make('small', 'text-muted mx-3', fmt(f.size)));
        li.appendChild(del);
        list.appendChild(li);
      });
    }

    function add(incoming) {
      var errs = [], next = files.slice(), ex = kept();
      Array.prototype.forEach.call(incoming, function (f) {
        var e = exts(f.name), last = e.length ? e[e.length - 1] : '';
        var bad = e.filter(function (x) { return cfg.deny.indexOf(x) >= 0; })[0];
        if (bad) { errs.push("'" + f.name + "': 첨부할 수 없는 형식(." + bad + ")입니다."); return; }
        if (cfg.allow.length && !e.length) { errs.push("'" + f.name + "': 확장자가 없는 파일은 첨부할 수 없습니다."); return; }
        if (cfg.allow.length && cfg.allow.indexOf(last) < 0) {
          errs.push("'" + f.name + "': 허용되지 않는 형식입니다. (허용: ." + cfg.allow.join(', .') + ')'); return;
        }
        if (cfg.maxFileSize !== null && f.size > cfg.maxFileSize) {
          errs.push("'" + f.name + "': 파일당 최대 " + fmt(cfg.maxFileSize) + '까지 가능합니다.'); return;
        }
        if (next.some(function (x) { return x.name === f.name && x.size === f.size && x.lastModified === f.lastModified; })) { return; }
        if (cfg.maxFiles !== null && ex.n + next.length >= cfg.maxFiles) {
          errs.push('파일은 최대 ' + cfg.maxFiles + '개까지 첨부할 수 있습니다.'); return;
        }
        if (cfg.maxTotal !== null && ex.size + sum(next) + f.size > cfg.maxTotal) {
          errs.push("'" + f.name + "': 전체 용량이 최대 " + fmt(cfg.maxTotal) + '를 넘습니다.'); return;
        }
        next.push(f);
      });
      files = next; sync(); render();
      showErrors(errs.filter(function (m, i) { return errs.indexOf(m) === i; }));
    }

    // 기존 파일 삭제 / 취소: hidden input {field}_delete 를 넣고 뺀다
    function toggleExisting(li, btn) {
      var h = li.__hidden;
      if (h) {  // 취소(되돌리기): 한도를 넘지 않을 때만
        var ex = kept(), size = parseInt(li.getAttribute('data-size'), 10) || 0;
        if ((cfg.maxFiles !== null && ex.n + files.length + 1 > cfg.maxFiles) ||
            (cfg.maxTotal !== null && ex.size + sum(files) + size > cfg.maxTotal)) {
          showErrors(['한도를 넘어 되돌릴 수 없습니다. 새로 추가한 파일을 먼저 삭제하세요.']); return;
        }
        root.removeChild(h); li.__hidden = null;
        li.classList.remove('attach-deleted'); btn.textContent = '삭제'; showErrors([]);
      } else {
        h = make('input'); h.type = 'hidden'; h.name = input.name + '_delete';
        h.value = li.getAttribute('data-id');
        root.appendChild(h); li.__hidden = h;
        li.classList.add('attach-deleted'); btn.textContent = '취소';
      }
    }
    list.addEventListener('click', function (e) {
      var btn = e.target;
      if (btn.classList.contains('attach-del') && btn.parentNode.getAttribute('data-id')) {
        toggleExisting(btn.parentNode, btn);
      }
    });

    trigger.addEventListener('click', function () { input.click(); });
    trigger.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); input.click(); }
    });
    input.addEventListener('change', function () { add(input.files); });

    if (cfg.drop) {
      var depth = 0;
      root.addEventListener('dragenter', function (e) { e.preventDefault(); depth++; root.classList.add('attach-dragover'); });
      root.addEventListener('dragover', function (e) { e.preventDefault(); });
      root.addEventListener('dragleave', function () { if (--depth <= 0) { depth = 0; root.classList.remove('attach-dragover'); } });
      root.addEventListener('drop', function (e) {
        e.preventDefault(); depth = 0; root.classList.remove('attach-dragover');
        if (e.dataTransfer && e.dataTransfer.files.length) { add(e.dataTransfer.files); }
      });
    }

    function reset() {
      files = []; sync(); render(); showErrors([]);
      Array.prototype.forEach.call(list.querySelectorAll('.attach-deleted'), function (li) {
        root.removeChild(li.__hidden); li.__hidden = null;
        li.classList.remove('attach-deleted');
        li.querySelector('.attach-del').textContent = '삭제';
      });
    }
    if (input.form) { input.form.addEventListener('reset', reset); }

    root.__attach = { add: add, reset: reset };
    return root.__attach;
  }

  function initAll(scope) {
    Array.prototype.forEach.call((scope || document).querySelectorAll('[data-attach]'), init);
  }

  // 컴포넌트(드롭 영역) 밖에 파일을 떨어뜨려도 브라우저가 파일을 열지 않게 막는다
  ['dragover', 'drop'].forEach(function (ev) {
    window.addEventListener(ev, function (e) {
      var t = e.target, inside = false;
      while (t && t.nodeType === 1) {
        if (t.getAttribute('data-ui') === 'drop') { inside = true; break; }
        t = t.parentNode;
      }
      if (!inside) { e.preventDefault(); }
    });
  });

  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', function () { initAll(); }); }
  else { initAll(); }
  window.Attach = { init: init, initAll: initAll };
})();
