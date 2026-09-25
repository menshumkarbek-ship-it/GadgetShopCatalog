/*
 * App-style dropdowns for every <select> on the site, and suggestion lists
 * for text inputs tied to a <datalist>.
 *
 * Native select and datalist popups are drawn by the operating system: they
 * look dated on Windows, different on every platform, and can't be styled.
 * So each one gets a stand-in drawn to match the site — a button that looks
 * exactly like the field it replaces (it takes the select's own classes),
 * and a rounded popover list.
 *
 * The native control stays in the page, hidden: it still holds the value,
 * submits with its form, fires `change` (so onchange handlers keep working),
 * and takes part in form validation. Put data-native on a <select> to keep
 * the browser's own dropdown.
 *
 * Keyboard follows the WAI-ARIA "select-only combobox" pattern: focus stays
 * on the button; arrows, Home/End, Enter/Space, Escape and type-to-jump work.
 */
(function () {
  'use strict';

  var CHEVRON = '<svg class="dd-chevron" viewBox="0 0 12 12" aria-hidden="true"><path d="M2.5 4.5 6 8l3.5-3.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  var CHECK = '<svg class="dd-check" viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 8.5l3 3 6-7" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  var MAX_HEIGHT = 320;
  var uid = 0;
  var current = null;  // the one popover open right now: {close: fn}

  function themeOf(el) {
    return el.closest('.product-management') ? 'panel' : 'store';
  }

  // ── The popover ─────────────────────────────────────────────────────────
  // Appended to <body> and positioned against the viewport, so no parent's
  // overflow or stacking can clip it. Built on open and removed on close,
  // which also means nothing is left behind when the panel swaps its
  // content out.

  function openPopover(anchor, theme, onClose) {
    if (current) current.close();
    var menu = document.createElement('div');
    menu.className = 'dd-menu';
    menu.id = 'dd-menu-' + (++uid);
    menu.dataset.theme = theme;
    menu.setAttribute('role', 'listbox');
    // A press inside the list must not take focus off the field.
    menu.addEventListener('mousedown', function (e) { e.preventDefault(); });

    function reposition() { place(menu, anchor); }
    function outside(e) {
      if (!menu.contains(e.target) && !anchor.contains(e.target)) handle.close();
    }
    var handle = {
      menu: menu,
      reposition: reposition,
      close: function () {
        if (current !== handle) return;
        current = null;
        menu.remove();
        window.removeEventListener('scroll', reposition, true);
        window.removeEventListener('resize', reposition);
        document.removeEventListener('pointerdown', outside, true);
        onClose();
      },
      show: function () {
        document.body.appendChild(menu);
        reposition();
      },
    };
    current = handle;
    window.addEventListener('scroll', reposition, true);
    window.addEventListener('resize', reposition);
    document.addEventListener('pointerdown', outside, true);
    return handle;
  }

  function place(menu, anchor) {
    var r = anchor.getBoundingClientRect();
    var vw = document.documentElement.clientWidth;
    var vh = window.innerHeight;
    var gap = 6, margin = 8;

    menu.style.minWidth = Math.min(Math.max(r.width, 176), vw - margin * 2) + 'px';
    menu.style.maxWidth = (vw - margin * 2) + 'px';
    menu.style.maxHeight = 'none';

    var below = vh - r.bottom - gap - margin;
    var above = r.top - gap - margin;
    // Downward, like a native dropdown, unless it would be cramped there
    // (under 200px) and there is more room above.
    var natural = Math.min(menu.scrollHeight, MAX_HEIGHT);
    var up = natural > below && below < 200 && above > below;
    var maxHeight = Math.max(120, Math.min(MAX_HEIGHT, up ? above : below));
    menu.style.maxHeight = maxHeight + 'px';

    var height = Math.min(menu.scrollHeight, maxHeight);
    var width = menu.offsetWidth;
    var left = r.left;
    if (left + width > vw - margin) left = Math.max(margin, r.right - width);

    menu.style.left = left + 'px';
    menu.style.top = (up ? r.top - gap - height : r.bottom + gap) + 'px';
    menu.dataset.side = up ? 'top' : 'bottom';
  }

  function makeOption(menu, index, text, selected, disabled) {
    var el = document.createElement('div');
    el.className = 'dd-option';
    el.id = menu.id + '-' + index;
    el.setAttribute('role', 'option');
    el.setAttribute('aria-selected', selected ? 'true' : 'false');
    if (disabled) el.setAttribute('aria-disabled', 'true');
    el.innerHTML = '<span class="dd-label"></span>' + CHECK;
    el.firstChild.textContent = text;
    menu.appendChild(el);
    return el;
  }

  function scrollIntoMenu(menu, el) {
    if (!el) return;
    var top = el.offsetTop, bottom = top + el.offsetHeight;
    if (top < menu.scrollTop) menu.scrollTop = top - 6;
    else if (bottom > menu.scrollTop + menu.clientHeight) menu.scrollTop = bottom - menu.clientHeight + 6;
  }

  // ── <select> ────────────────────────────────────────────────────────────

  function enhanceSelect(select) {
    if (select.dataset.dd || select.multiple || select.size > 1 || select.hasAttribute('data-native')) return;
    select.dataset.dd = 'select';
    var theme = themeOf(select);

    var button = document.createElement('button');
    button.type = 'button';
    button.className = select.className + ' dd-trigger';
    button.dataset.theme = theme;
    button.setAttribute('role', 'combobox');
    button.setAttribute('aria-haspopup', 'listbox');
    button.setAttribute('aria-expanded', 'false');
    button.innerHTML = '<span class="dd-value"></span>' + CHEVRON;
    var valueEl = button.firstChild;
    select.insertAdjacentElement('afterend', button);

    // The native select stays for the form, out of sight and out of the
    // tab order; its label now names the button.
    select.classList.add('dd-native');
    select.tabIndex = -1;
    select.setAttribute('aria-hidden', 'true');
    var label = select.labels && select.labels[0];
    if (label) {
      label.id = label.id || 'dd-label-' + (++uid);
      // Named by the label; the combobox's own text is read as its value.
      button.setAttribute('aria-labelledby', label.id);
      label.addEventListener('click', function (e) { e.preventDefault(); button.focus(); });
    } else if (select.getAttribute('aria-label')) {
      button.setAttribute('aria-label', select.getAttribute('aria-label'));
    }

    var popover = null, items = [], active = -1, typed = '', typedAt = 0;

    function sync() {
      var opt = select.options[select.selectedIndex];
      valueEl.textContent = opt ? opt.text : '';
      button.classList.toggle('dd-placeholder', !opt || opt.value === '');
      button.disabled = select.disabled;
    }

    function setActive(i) {
      if (!popover || !items.length) return;
      i = Math.max(0, Math.min(items.length - 1, i));
      if (items[active]) items[active].el.classList.remove('is-active');
      active = i;
      items[i].el.classList.add('is-active');
      button.setAttribute('aria-activedescendant', items[i].el.id);
      scrollIntoMenu(popover.menu, items[i].el);
    }

    function step(from, delta) {
      // The next option that isn't disabled, `delta` places from `from`.
      var i = from;
      for (var n = 0; n < items.length; n++) {
        i += delta;
        if (i < 0 || i >= items.length) return from;
        if (!items[i].option.disabled) return i;
      }
      return from;
    }

    function open() {
      if (popover || select.disabled) return;
      popover = openPopover(button, theme, function () {
        popover = null; items = []; active = -1;
        button.setAttribute('aria-expanded', 'false');
        button.removeAttribute('aria-activedescendant');
        button.removeAttribute('aria-controls');
      });
      var menu = popover.menu;
      Array.prototype.forEach.call(select.children, function (node) {
        if (node.tagName === 'OPTGROUP') {
          var group = document.createElement('div');
          group.className = 'dd-group';
          group.setAttribute('role', 'presentation');
          group.textContent = node.label;
          menu.appendChild(group);
          Array.prototype.forEach.call(node.children, add);
        } else if (node.tagName === 'OPTION') {
          add(node);
        }
      });
      function add(option) {
        if (option.hidden) return;
        var el = makeOption(menu, items.length, option.text, option.selected, option.disabled);
        items.push({el: el, option: option});
      }
      menu.addEventListener('click', function (e) {
        var el = e.target.closest('.dd-option');
        if (!el) return;
        var i = items.findIndex(function (item) { return item.el === el; });
        if (i > -1 && !items[i].option.disabled) choose(i);
      });
      menu.addEventListener('mousemove', function (e) {
        var el = e.target.closest('.dd-option');
        if (!el || el.classList.contains('is-active')) return;
        var i = items.findIndex(function (item) { return item.el === el; });
        if (i > -1 && !items[i].option.disabled) setActive(i);
      });
      button.setAttribute('aria-expanded', 'true');
      button.setAttribute('aria-controls', menu.id);
      popover.show();
      var selected = items.findIndex(function (item) { return item.option.selected; });
      setActive(selected > -1 ? selected : step(-1, 1));
    }

    function close() { if (popover) popover.close(); }

    function choose(i) {
      var option = items[i].option;
      close();
      button.focus();
      if (select.selectedIndex !== option.index) {
        select.selectedIndex = option.index;
        select.dispatchEvent(new Event('input', {bubbles: true}));
        select.dispatchEvent(new Event('change', {bubbles: true}));
      }
      sync();
    }

    function typeahead(ch) {
      var now = Date.now();
      typed = (now - typedAt > 600 ? '' : typed) + ch.toLowerCase();
      typedAt = now;
      var start = typed.length === 1 ? active + 1 : active;
      for (var n = 0; n < items.length; n++) {
        var i = (start + n) % items.length;
        if (!items[i].option.disabled && items[i].option.text.trim().toLowerCase().indexOf(typed) === 0) {
          setActive(i);
          return;
        }
      }
    }

    button.addEventListener('click', function () { popover ? close() : open(); });
    button.addEventListener('keydown', function (e) {
      var key = e.key;
      if (!popover) {
        if (key === 'ArrowDown' || key === 'ArrowUp' || key === 'Enter' || key === ' ') {
          e.preventDefault();
          open();
        } else if (key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
          open();
          typeahead(key);
        }
        return;
      }
      if (key === 'ArrowDown') { e.preventDefault(); setActive(step(active, 1)); }
      else if (key === 'ArrowUp') { e.preventDefault(); setActive(step(active, -1)); }
      else if (key === 'Home') { e.preventDefault(); setActive(step(-1, 1)); }
      else if (key === 'End') { e.preventDefault(); setActive(step(items.length, -1)); }
      else if (key === 'PageDown') { e.preventDefault(); setActive(Math.min(items.length - 1, active + 8)); }
      else if (key === 'PageUp') { e.preventDefault(); setActive(Math.max(0, active - 8)); }
      else if (key === 'Enter' || key === ' ') { e.preventDefault(); if (active > -1) choose(active); }
      else if (key === 'Escape') { e.preventDefault(); close(); }
      else if (key === 'Tab') { close(); }
      else if (key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) { e.preventDefault(); typeahead(key); }
    });
    button.addEventListener('blur', function () {
      // Focus left for somewhere else (not a press inside the list, which
      // keeps it): the list goes too.
      setTimeout(function () { if (document.activeElement !== button) close(); }, 0);
    });

    // Stay in step with changes made from outside: another script setting
    // the value, a form reset, options swapped in.
    select.addEventListener('change', function () { sync(); clearInvalid(); });
    if (select.form) select.form.addEventListener('reset', function () { setTimeout(function () { sync(); clearInvalid(); }, 0); });
    new MutationObserver(sync).observe(select, {childList: true, subtree: true, attributes: true, attributeFilter: ['disabled']});

    // Validation: the hidden select can't show the browser's bubble or take
    // focus, so the button shows the problem instead.
    var errorEl = null;
    select.addEventListener('invalid', function (e) {
      e.preventDefault();
      button.classList.add('dd-invalid');
      if (!errorEl) {
        errorEl = document.createElement('p');
        errorEl.className = 'dd-error';
        errorEl.setAttribute('role', 'alert');
        button.insertAdjacentElement('afterend', errorEl);
      }
      errorEl.textContent = select.validationMessage;
      if (!document.activeElement || !document.activeElement.classList.contains('dd-invalid')) {
        button.focus();
        button.scrollIntoView({block: 'center', behavior: 'smooth'});
      }
    });
    function clearInvalid() {
      if (select.checkValidity()) {
        button.classList.remove('dd-invalid');
        if (errorEl) { errorEl.remove(); errorEl = null; }
      }
    }

    sync();
  }

  // ── <input list="…"> ────────────────────────────────────────────────────
  // Suggestions the admin may pick or ignore: the field stays free text.

  function enhanceSuggestions(input) {
    var datalist = document.getElementById(input.getAttribute('list') || '');
    if (!datalist || input.dataset.dd) return;
    input.dataset.dd = 'suggest';
    input.removeAttribute('list');  // switches the browser's own popup off
    input.setAttribute('role', 'combobox');
    input.setAttribute('aria-autocomplete', 'list');
    input.setAttribute('aria-expanded', 'false');
    input.setAttribute('autocomplete', 'off');
    var theme = themeOf(input);
    var popover = null, items = [], active = -1;

    function values() {
      return Array.prototype.map.call(datalist.options, function (o) { return o.value; }).filter(Boolean);
    }

    function matches() {
      var q = input.value.trim().toLowerCase();
      return values().filter(function (v) {
        var low = v.toLowerCase();
        return !q || (low.indexOf(q) > -1 && low !== q);
      }).slice(0, 50);
    }

    function render() {
      var found = matches();
      if (!found.length) { close(); return; }
      if (!popover) {
        popover = openPopover(input, theme, function () {
          popover = null; items = []; active = -1;
          input.setAttribute('aria-expanded', 'false');
          input.removeAttribute('aria-activedescendant');
        });
        popover.menu.addEventListener('click', function (e) {
          var el = e.target.closest('.dd-option');
          var i = items.findIndex(function (item) { return item.el === el; });
          if (i > -1) pick(i);
        });
        input.setAttribute('aria-expanded', 'true');
        input.setAttribute('aria-controls', popover.menu.id);
        popover.show();
      }
      var menu = popover.menu;
      menu.innerHTML = '';
      items = [];
      active = -1;
      input.removeAttribute('aria-activedescendant');
      var q = input.value.trim().toLowerCase();
      found.forEach(function (value) {
        var el = makeOption(menu, items.length, '', false, false);
        highlight(el.firstChild, value, q);
        items.push({el: el, value: value});
      });
      popover.reposition();
    }

    function highlight(target, value, q) {
      var at = q ? value.toLowerCase().indexOf(q) : -1;
      if (at < 0) { target.textContent = value; return; }
      var mark = document.createElement('mark');
      mark.textContent = value.slice(at, at + q.length);
      target.append(value.slice(0, at), mark, value.slice(at + q.length));
    }

    function setActive(i) {
      if (!items.length) return;
      if (items[active]) items[active].el.classList.remove('is-active');
      active = (i + items.length) % items.length;
      items[active].el.classList.add('is-active');
      input.setAttribute('aria-activedescendant', items[active].el.id);
      scrollIntoMenu(popover.menu, items[active].el);
    }

    function pick(i) {
      input.value = items[i].value;
      close();
      // Untrusted, so the input listener below doesn't reopen the list.
      input.dispatchEvent(new Event('input', {bubbles: true}));
      input.dispatchEvent(new Event('change', {bubbles: true}));
    }

    function close() { if (popover) popover.close(); }

    input.addEventListener('focus', render);
    input.addEventListener('click', function () { if (!popover) render(); });
    input.addEventListener('input', function (e) { if (e.isTrusted) render(); });
    input.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown') { e.preventDefault(); popover ? setActive(active + 1) : render(); }
      else if (e.key === 'ArrowUp' && popover) { e.preventDefault(); setActive(active - 1); }
      else if (e.key === 'Enter' && popover && active > -1) { e.preventDefault(); pick(active); }
      else if (e.key === 'Escape' && popover) { e.preventDefault(); close(); }
      else if (e.key === 'Tab') { close(); }
    });
    input.addEventListener('blur', function () { setTimeout(close, 0); });
  }

  // ── Wiring ──────────────────────────────────────────────────────────────

  function enhance(root) {
    if (root.nodeType !== 1) return;
    if (root.matches('select')) enhanceSelect(root);
    else if (root.matches('input[list]')) enhanceSuggestions(root);
    root.querySelectorAll('select').forEach(enhanceSelect);
    root.querySelectorAll('input[list]').forEach(enhanceSuggestions);
  }

  enhance(document.body);
  // The management panel swaps content in without a page load; whatever
  // it brings in gets the same treatment.
  new MutationObserver(function (mutations) {
    mutations.forEach(function (m) { m.addedNodes.forEach(enhance); });
  }).observe(document.body, {childList: true, subtree: true});
})();
