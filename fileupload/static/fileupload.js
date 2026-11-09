/* Bootstrap 4 파일 업로드 컴포넌트. [data-fileupload] 요소를 자동 초기화한다.
 * 파일은 네이티브 <input type=file>.files 에 동기화되므로 일반 폼 submit 으로 전송된다. */
(function () {
  'use strict';

  function fmt(n) {
    var u = ['B', 'KB', 'MB', 'GB'], i = 0;
    while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
    return (i === 0 ? n : n.toFixed(1)) + u[i];
  }
  function list(v) { return v ? v.split(',').filter(Boolean) : []; }
  function exts(name) { return name.toLowerCase().split('.').slice(1).filter(Boolean); }

  var DOC_TYPES = {
    pdf: 'pdf', doc: 'word', docx: 'word', hwp: 'hwp', hwpx: 'hwp',
    xls: 'excel', xlsx: 'excel', csv: 'excel', ppt: 'ppt', pptx: 'ppt',
    zip: 'zip', rar: 'zip', '7z': 'zip', txt: 'txt'
  };
  // 이미지가 아닌 파일용 문서 모양 아이콘 (확장자 표시)
  function docIcon(name) {
    var e = exts(name), ext = e.length ? e[e.length - 1] : '';
    var el = document.createElement('span');
    el.className = 'fu-doc fu-doc-' + (DOC_TYPES[ext] || 'etc');
    el.setAttribute('aria-hidden', 'true');
    el.textContent = ext.slice(0, 4).toUpperCase();
    return el;
  }

  function init(root) {
    if (root.__fu) return root.__fu;
    var d = root.dataset;
    var cfg = {
      multiple: d.multiple !== 'false',
      maxFiles: d.maxFiles ? +d.maxFiles : null,
      maxFileSize: d.maxFileSize ? +d.maxFileSize : null,
      maxTotal: d.maxTotalSize ? +d.maxTotalSize : null,
      allow: list(d.allow), deny: list(d.deny), required: d.required === 'true'
    };
    var drop = root.querySelector('.fu-drop');
    var input = root.querySelector('.fu-input');
    var errBox = root.querySelector('.fu-errors');
    var ul = root.querySelector('.fu-list');
    var files = [];

    function sync() {
      var dt = new DataTransfer();
      files.forEach(function (f) { dt.items.add(f); });
      input.files = dt.files;
      input.required = cfg.required && files.length === 0;
    }

    function showErrors(errs) {
      errBox.innerHTML = '';
      errs.forEach(function (m) {
        var div = document.createElement('div');
        div.textContent = m;
        errBox.appendChild(div);
      });
      errBox.classList.toggle('d-none', errs.length === 0);
    }

    function render() {
      ul.innerHTML = '';
      files.forEach(function (f, idx) {
        var li = document.createElement('li');
        li.className = 'list-group-item d-flex align-items-center py-2';
        if (f.type.indexOf('image/') === 0) {
          var img = document.createElement('img');
          img.className = 'fu-thumb';
          img.src = URL.createObjectURL(f);
          img.onload = function () { URL.revokeObjectURL(img.src); };
          li.appendChild(img);
        } else {
          li.appendChild(docIcon(f.name));
        }
        var name = document.createElement('span');
        name.className = 'fu-item-name flex-grow-1';
        name.textContent = f.name;
        var size = document.createElement('small');
        size.className = 'text-muted mx-3';
        size.textContent = fmt(f.size);
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'btn btn-sm btn-outline-danger';
        btn.textContent = '삭제';
        btn.addEventListener('click', function () {
          files.splice(idx, 1); sync(); render(); showErrors([]);
        });
        li.appendChild(name); li.appendChild(size); li.appendChild(btn);
        ul.appendChild(li);
      });
    }

    function add(incoming) {
      var errs = [];
      var list = cfg.multiple ? files.slice() : [];
      Array.prototype.forEach.call(incoming, function (f) {
        var e = exts(f.name), last = e[e.length - 1] || '';
        var bad = e.filter(function (x) { return cfg.deny.indexOf(x) >= 0; })[0];
        if (bad) { errs.push("'" + f.name + "': 업로드가 금지된 형식(." + bad + ")입니다."); return; }
        if (cfg.allow.length && cfg.allow.indexOf(last) < 0) {
          errs.push("'" + f.name + "': 허용되지 않는 형식입니다. (허용: ." + cfg.allow.join(', .') + ')'); return;
        }
        if (cfg.maxFileSize && f.size > cfg.maxFileSize) {
          errs.push("'" + f.name + "': 파일당 최대 " + fmt(cfg.maxFileSize) + '까지 가능합니다.'); return;
        }
        if (list.some(function (x) { return x.name === f.name && x.size === f.size && x.lastModified === f.lastModified; })) return;
        if (cfg.maxFiles && list.length >= cfg.maxFiles) {
          errs.push('파일은 최대 ' + cfg.maxFiles + '개까지 업로드할 수 있습니다.'); return;
        }
        var total = list.reduce(function (s, x) { return s + x.size; }, 0) + f.size;
        if (cfg.maxTotal && total > cfg.maxTotal) {
          errs.push("'" + f.name + "': 전체 용량이 최대 " + fmt(cfg.maxTotal) + '를 초과합니다.'); return;
        }
        list.push(f);
      });
      files = list; sync(); render();
      showErrors(errs.filter(function (m, i) { return errs.indexOf(m) === i; }));
    }

    drop.addEventListener('click', function () { input.click(); });
    drop.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); input.click(); }
    });
    input.addEventListener('change', function () { add(input.files); });

    var depth = 0;
    root.addEventListener('dragenter', function (e) { e.preventDefault(); depth++; root.classList.add('fu-dragover'); });
    root.addEventListener('dragover', function (e) { e.preventDefault(); });
    root.addEventListener('dragleave', function () { if (--depth <= 0) { depth = 0; root.classList.remove('fu-dragover'); } });
    root.addEventListener('drop', function (e) {
      e.preventDefault(); depth = 0; root.classList.remove('fu-dragover');
      if (e.dataTransfer && e.dataTransfer.files.length) add(e.dataTransfer.files);
    });

    var form = input.form;
    if (form) form.addEventListener('reset', function () { files = []; render(); showErrors([]); });

    sync();
    root.__fu = { add: add, clear: function () { files = []; sync(); render(); showErrors([]); }, getFiles: function () { return files.slice(); } };
    return root.__fu;
  }

  function initAll(scope) {
    (scope || document).querySelectorAll('[data-fileupload]').forEach(init);
  }

  // 탐색기 파일을 컴포넌트 밖에 떨어뜨렸을 때 브라우저가 파일을 열어버리는 것을 방지
  ['dragover', 'drop'].forEach(function (ev) {
    window.addEventListener(ev, function (e) {
      if (!e.target.closest || !e.target.closest('[data-fileupload]')) e.preventDefault();
    });
  });

  document.addEventListener('DOMContentLoaded', function () {
    initAll();
    // 동적으로 추가되는 컴포넌트도 자동 초기화
    new MutationObserver(function () { initAll(); }).observe(document.body, { childList: true, subtree: true });
  });
  window.FileUpload = { init: init, initAll: initAll };
})();
