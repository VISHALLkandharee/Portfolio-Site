/* Vishal Kumar portfolio, v3 */
(function () {
  'use strict';
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------- theme ---------- */
  var themeBtn = document.querySelector('.theme-toggle');
  function paintTheme() {
    var t = document.documentElement.getAttribute('data-theme') || 'dark';
    if (themeBtn) {
      themeBtn.textContent = t === 'light' ? '☾' : '☀';
      themeBtn.setAttribute('aria-label', t === 'light' ? 'Switch to dark theme' : 'Switch to light theme');
    }
  }
  paintTheme();
  if (themeBtn) {
    themeBtn.addEventListener('click', function () {
      var next = (document.documentElement.getAttribute('data-theme') === 'light') ? 'dark' : 'light';
      document.documentElement.setAttribute('data-theme', next);
      try { localStorage.setItem('vk-theme', next); } catch (e) {}
      paintTheme();
    });
  }

  /* ---------- mobile nav ---------- */
  var toggle = document.querySelector('.nav-toggle');
  var nav = document.getElementById('nav');
  if (toggle && nav) {
    toggle.addEventListener('click', function () {
      var open = nav.classList.toggle('open');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      toggle.textContent = open ? '✕' : '☰';
    });
    nav.addEventListener('click', function (e) {
      if (e.target.tagName === 'A') {
        nav.classList.remove('open');
        toggle.setAttribute('aria-expanded', 'false');
        toggle.textContent = '☰';
      }
    });
  }

  /* ---------- scroll progress ---------- */
  var bar = document.querySelector('.progress');
  if (bar) {
    var tick = function () {
      var h = document.documentElement.scrollHeight - window.innerHeight;
      bar.style.width = (h > 0 ? (window.scrollY / h) * 100 : 0) + '%';
    };
    window.addEventListener('scroll', tick, { passive: true });
    window.addEventListener('resize', tick);
    tick();
  }

  /* ---------- reveal on scroll ---------- */
  var revealables = document.querySelectorAll('.reveal');
  if (!('IntersectionObserver' in window) || reduced) {
    Array.prototype.forEach.call(revealables, function (el) { el.classList.add('in'); });
  } else {
    var ro = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('in');
          ro.unobserve(entry.target);
        }
      });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });
    Array.prototype.forEach.call(revealables, function (el, i) {
      el.style.transitionDelay = Math.min(i % 4, 3) * 70 + 'ms';
      ro.observe(el);
    });
  }

  /* ---------- active nav link ---------- */
  var links = Array.prototype.slice.call(document.querySelectorAll('.nav a[href^="#"]'));
  var sections = links.map(function (a) { return document.querySelector(a.getAttribute('href')); }).filter(Boolean);
  if ('IntersectionObserver' in window && sections.length) {
    var so = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        links.forEach(function (a) {
          a.classList.toggle('active', a.getAttribute('href') === '#' + entry.target.id);
        });
      });
    }, { rootMargin: '-45% 0px -50% 0px' });
    sections.forEach(function (s) { so.observe(s); });
  }

  /* ---------- typed role line ---------- */
  var typed = document.querySelector('.typed');
  if (typed) {
    var phrases = (typed.getAttribute('data-phrases') || '').split('|').filter(Boolean);
    var out = typed.querySelector('.out');
    if (phrases.length && out) {
      if (reduced) {
        out.textContent = phrases[0];
      } else {
        var pi = 0, ci = 0, deleting = false;
        var run = function () {
          var word = phrases[pi];
          out.textContent = word.slice(0, ci);
          if (!deleting && ci < word.length) { ci++; setTimeout(run, 55); }
          else if (!deleting) { deleting = true; setTimeout(run, 1900); }
          else if (ci > 0) { ci--; setTimeout(run, 26); }
          else { deleting = false; pi = (pi + 1) % phrases.length; setTimeout(run, 300); }
        };
        run();
      }
    }
  }

  /* ---------- count up stats ---------- */
  var counters = document.querySelectorAll('[data-count]');
  if (counters.length && 'IntersectionObserver' in window && !reduced) {
    var co = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        var el = entry.target;
        co.unobserve(el);
        var target = parseFloat(el.getAttribute('data-count'));
        var suffix = el.getAttribute('data-suffix') || '';
        var decimals = (String(target).split('.')[1] || '').length;
        var start = null, dur = 1200;
        var step = function (ts) {
          if (!start) start = ts;
          var p = Math.min((ts - start) / dur, 1);
          var eased = 1 - Math.pow(1 - p, 3);
          el.textContent = (target * eased).toFixed(decimals) + suffix;
          if (p < 1) requestAnimationFrame(step);
        };
        requestAnimationFrame(step);
      });
    }, { threshold: 0.4 });
    Array.prototype.forEach.call(counters, function (el) { co.observe(el); });
  }

  /* ---------- pointer glow on project cards ---------- */
  if (!reduced && window.matchMedia('(hover: hover)').matches) {
    Array.prototype.forEach.call(document.querySelectorAll('.project'), function (card) {
      card.addEventListener('mousemove', function (e) {
        var r = card.getBoundingClientRect();
        card.style.setProperty('--mx', ((e.clientX - r.left) / r.width) * 100 + '%');
        card.style.setProperty('--my', ((e.clientY - r.top) / r.height) * 100 + '%');
      });
    });
  }

  /* ---------- copy to clipboard ---------- */
  Array.prototype.forEach.call(document.querySelectorAll('[data-copy]'), function (btn) {
    btn.addEventListener('click', function () {
      var value = btn.getAttribute('data-copy');
      var done = function () {
        var old = btn.textContent;
        btn.textContent = 'copied';
        setTimeout(function () { btn.textContent = old; }, 1600);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(value).then(done, function () {});
      } else {
        var ta = document.createElement('textarea');
        ta.value = value; document.body.appendChild(ta); ta.select();
        try { document.execCommand('copy'); done(); } catch (e) {}
        document.body.removeChild(ta);
      }
    });
  });

  /* ---------- contact form ---------- */
  var form = document.getElementById('contact-form');
  if (form) {
    var status = document.getElementById('form-status');
    var submit = form.querySelector('button[type="submit"]');
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      Array.prototype.forEach.call(form.querySelectorAll('.field'), function (f) { f.classList.remove('invalid'); });
      status.className = 'form-status';
      status.textContent = '';
      var label = submit.textContent;
      submit.disabled = true;
      submit.textContent = 'Sending…';

      var values = {
        name: (form.querySelector('[name="name"]') || {}).value || '',
        email: (form.querySelector('[name="email"]') || {}).value || '',
        subject: (form.querySelector('[name="subject"]') || {}).value || '',
        message: (form.querySelector('[name="message"]') || {}).value || ''
      };

      function reveal(el) {
        if (el.scrollIntoView) {
          try { el.scrollIntoView({ behavior: 'smooth', block: 'center' }); }
          catch (err) { el.scrollIntoView(); }
        }
      }

      function fail(text) {
        status.className = 'form-status bad';
        status.textContent = text;
        reveal(status);
      }

      function showSuccess(sent) {
        var handoff =
          'Hi Vishal, I just sent this through your website.\n\n' +
          'Name: ' + sent.name + '\n' +
          'Email: ' + sent.email + '\n' +
          'About: ' + sent.subject + '\n\n' + sent.message;
        var panel = document.createElement('div');
        panel.className = 'sent-panel';
        panel.setAttribute('role', 'status');
        panel.innerHTML =
          '<span class="sent-tick" aria-hidden="true">✓</span>' +
          '<h3>Got it, ' + escapeHtml(sent.name.split(' ')[0] || 'thanks') + '</h3>' +
          '<p>Your message is saved in my inbox and I have your address, ' +
          escapeHtml(sent.email) + '. I reply to every serious enquiry, usually within one working day.</p>' +
          '<p class="sent-sub">Want it in front of me right now? Send the same message straight to my phone or my email.</p>' +
          '<div class="sent-actions">' +
            '<a class="btn btn-primary" target="_blank" rel="noopener" href="https://wa.me/923000249930?text=' +
              encodeURIComponent(handoff) + '">Also send on WhatsApp</a>' +
            '<a class="btn btn-ghost" href="mailto:vishall.kandharee@gmail.com?subject=' +
              encodeURIComponent(sent.subject || 'Enquiry from your website') + '&body=' +
              encodeURIComponent(handoff) + '">Also send by email</a>' +
            '<button class="btn btn-ghost" type="button" data-again>Write another message</button>' +
          '</div>';
        form.style.display = 'none';
        status.className = 'form-status';
        status.textContent = '';
        form.parentNode.insertBefore(panel, form.nextSibling);
        reveal(panel);
        var again = panel.querySelector('[data-again]');
        if (again) {
          again.addEventListener('click', function () {
            panel.parentNode.removeChild(panel);
            form.reset();
            form.style.display = '';
            reveal(form);
          });
        }
      }

      function escapeHtml(value) {
        return String(value).replace(/[&<>"']/g, function (ch) {
          return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch];
        });
      }

      fetch('/api/contact', {
        method: 'POST',
        body: new FormData(form),
        headers: { 'X-Requested-With': 'fetch', 'Accept': 'application/json' }
      })
        .then(function (r) {
          return r.text().then(function (text) {
            var data = null;
            try { data = JSON.parse(text); } catch (e) { data = null; }
            return { ok: r.ok, data: data };
          });
        })
        .then(function (res) {
          // No body, or a body we cannot parse, still counts as delivered
          // when the server answered with a success status.
          var delivered = res.ok && (!res.data || res.data.ok !== false);
          if (delivered) {
            showSuccess(values);
          } else if (res.data && res.data.errors) {
            Object.keys(res.data.errors).forEach(function (key) {
              var field = form.querySelector('[name="' + key + '"]');
              var wrap = field && field.closest ? field.closest('.field') : null;
              if (wrap) {
                wrap.classList.add('invalid');
                var err = wrap.querySelector('.err');
                if (err) err.textContent = res.data.errors[key];
              }
            });
            fail('Please check the highlighted fields and send again.');
          } else {
            fail((res.data && res.data.error) || 'Something went wrong at my end. Please email vishall.kandharee@gmail.com directly.');
          }
        })
        .catch(function () {
          fail('Your connection dropped before the message was sent. Please email vishall.kandharee@gmail.com or message +92 300 0249930 on WhatsApp.');
        })
        .then(function () {
          submit.disabled = false;
          submit.textContent = label;
        });
    });
  }

  /* ---------- owner badge ----------
     Shows only for a signed-in owner. The marker cookie carries no
     authority: the unread count is served only against a valid session. */
  (function () {
    if (!/(^|;\s*)vk_owner=1/.test(document.cookie)) return;
    if (window.location.pathname.indexOf('/inbox') === 0) return;
    fetch('/api/inbox/unread', { headers: { 'Accept': 'application/json' } })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data || !data.signedIn) return;
        var link = document.createElement('a');
        link.className = 'owner-badge';
        link.href = '/inbox';
        link.innerHTML = '<span class="owner-dot"></span>Inbox' +
          (data.unread ? ' <b>' + data.unread + '</b>' : '');
        link.title = data.unread
          ? data.unread + ' unread message' + (data.unread === 1 ? '' : 's')
          : 'No unread messages';
        document.body.appendChild(link);
      })
      .catch(function () {});
  })();

  /* ---------- year ---------- */
  var year = document.getElementById('year');
  if (year) year.textContent = new Date().getFullYear();
})();
