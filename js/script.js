function typeTerminal(el, lines, opts) {
  opts = opts || {};
  var charDelay = opts.charDelay || 16;
  var lineDelay = opts.lineDelay || 260;
  el.innerHTML = '';

  function finalize(div, text) {
    if (text.indexOf('$ ') === 0) {
      div.innerHTML = '<span class="prompt">$</span> ' + text.slice(2);
    }
  }

  var li = 0;
  function nextLine() {
    if (li >= lines.length) return;
    var item = lines[li];
    var div = document.createElement('div');
    if (item.cls) div.className = item.cls;
    var cursor = document.createElement('span');
    cursor.className = 'cursor';
    div.appendChild(cursor);
    el.appendChild(div);

    var text = item.text;
    var ci = 0;
    (function nextChar() {
      if (ci < text.length) {
        cursor.insertAdjacentText('beforebegin', text[ci]);
        ci++;
        setTimeout(nextChar, charDelay);
      } else {
        cursor.remove();
        finalize(div, text);
        li++;
        setTimeout(nextLine, lineDelay);
      }
    })();
  }
  nextLine();
}

document.addEventListener('DOMContentLoaded', function () {
  var heroTerm = document.getElementById('hero-terminal-body');
  if (heroTerm) {
    typeTerminal(heroTerm, [
      { text: '$ databricks jobs run-now medallion-pipeline-dev' },
      { text: 'bronze_ingest... OK', cls: 'ok' },
      { text: 'silver_transform... OK', cls: 'ok' },
      { text: 'gold_aggregate... OK', cls: 'ok' },
      { text: 'validate_counts... OK', cls: 'ok' },
      { text: 'Pipeline completed successfully \u2713', cls: 'out' }
    ]);
  }

  var projTerm = document.getElementById('project-terminal-body');
  if (projTerm) {
    typeTerminal(projTerm, [
      { text: '$ terraform apply -var env=prod' },
      { text: 'databricks_job.medallion_pipeline: creating...' },
      { text: 'databricks_job.medallion_pipeline: creation complete' },
      { text: 'Apply complete. 6 resources added, 0 changed, 0 destroyed \u2713', cls: 'ok' }
    ]);
  }

  var root = document.documentElement;
  var saved = localStorage.getItem('theme');
  var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  if (saved === 'dark' || (!saved && prefersDark)) root.classList.add('dark');

  var btn = document.getElementById('theme-toggle');
  if (btn) {
    btn.addEventListener('click', function () {
      root.classList.toggle('dark');
      localStorage.setItem('theme', root.classList.contains('dark') ? 'dark' : 'light');
    });
  }
});
