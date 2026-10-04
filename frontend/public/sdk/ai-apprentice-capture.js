/*
 * AI Apprentice Capture SDK
 * -------------------------
 * Drop this script into any web application to stream structured events to an
 * AI Apprentice capture session, so the Work Map is built from what you actually
 * do — not from a scripted demo.
 *
 * Quick start:
 *   <script src="http://localhost:3000/sdk/ai-apprentice-capture.js"></script>
 *   <script>
 *     AIApprentice.init({
 *       apiUrl: "http://localhost:8000",
 *       sessionId: "<SESSION_ID_FROM_THE_CAPTURE_UI>",
 *       source: "my_real_app",
 *       autoTrack: true
 *     });
 *   </script>
 *
 * Or via script tag data attributes (auto-inits):
 *   <script src=".../ai-apprentice-capture.js"
 *           data-api-url="http://localhost:8000"
 *           data-session-id="..."
 *           data-auto-track="true"></script>
 *
 * Privacy: nothing is sent unless a session is actively capturing. Pause and
 * Off Record in the capture UI stop telemetry within one status poll. Password
 * fields and elements marked data-ai-apprentice-ignore are never captured.
 */
(function (global) {
  "use strict";

  var STORAGE_KEY = "ai_apprentice.config";
  var DEFAULTS = {
    apiUrl: "http://localhost:8000",
    sessionId: null,
    source: "web_app",
    autoTrack: false,
    pollMs: 3000,
  };

  var config = Object.assign({}, DEFAULTS, load());
  var remoteStatus = "unknown";
  var pollTimer = null;
  var tracked = false;
  var lastValues = new WeakMap();

  function load() {
    try {
      return JSON.parse(global.localStorage.getItem(STORAGE_KEY) || "{}");
    } catch {
      return {};
    }
  }

  function save() {
    try {
      global.localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
    } catch {
      /* storage may be unavailable */
    }
  }

  function uuid() {
    if (global.crypto && global.crypto.randomUUID) return global.crypto.randomUUID();
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
      var r = (Math.random() * 16) | 0;
      var v = c === "x" ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }

  function endpoint(path) {
    return config.apiUrl.replace(/\/$/, "") + "/api/sessions/" + config.sessionId + path;
  }

  function shouldSend() {
    return !!config.sessionId && remoteStatus === "capturing";
  }

  function emit(type, data) {
    if (!type) return Promise.resolve(null);
    if (!shouldSend()) return Promise.resolve(null);
    return fetch(endpoint("/events"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      keepalive: true,
      body: JSON.stringify({
        client_event_id: uuid(),
        timestamp_ms: Date.now(),
        source: config.source,
        type: type,
        data: data || {},
      }),
    })
      .then(function (res) {
        return res.ok ? res.json() : null;
      })
      .catch(function () {
        return null;
      });
  }

  function syncStatus() {
    if (!config.sessionId) return;
    fetch(endpoint(""), { cache: "no-store" })
      .then(function (res) {
        return res.ok ? res.json() : null;
      })
      .then(function (body) {
        if (body && body.status) remoteStatus = body.status;
      })
      .catch(function () {
        /* keep last known status on transient errors */
      });
  }

  function attachAutoTrack() {
    if (tracked) return;
    tracked = true;

    document.addEventListener(
      "click",
      function (e) {
        var el = e.target && e.target.closest
          ? e.target.closest("button, a, [role=button], input[type=submit], [data-ai-apprentice]")
          : null;
        if (!el || isIgnored(el)) return;
        var type = el.getAttribute("data-ai-apprentice") || "click";
        emit(type, {
          label: (el.getAttribute("aria-label") || el.textContent || "").trim().slice(0, 120),
          element: el.tagName.toLowerCase(),
        });
      },
      true
    );

    document.addEventListener(
      "change",
      function (e) {
        var el = e.target;
        if (!el || !el.matches || !el.matches("input, select, textarea") || isIgnored(el)) return;
        if (el.type === "password") return;
        var field = el.name || el.id || el.getAttribute("data-ai-apprentice-field") || null;
        var oldValue = lastValues.get(el);
        lastValues.set(el, el.value);
        emit(el.getAttribute("data-ai-apprentice") || "field_changed", {
          field: field,
          old_value: oldValue,
          new_value: el.value,
        });
      },
      true
    );

    document.addEventListener(
      "submit",
      function (e) {
        var form = e.target;
        if (!form || isIgnored(form)) return;
        emit(form.getAttribute("data-ai-apprentice") || "save_attempted", {
          form: form.id || form.name || null,
        });
      },
      true
    );
  }

  function isIgnored(el) {
    return !!(el.closest && el.closest("[data-ai-apprentice-ignore]"));
  }

  var AIApprentice = {
    init: function (options) {
      config = Object.assign({}, DEFAULTS, config, options || {});
      save();
      syncStatus();
      if (pollTimer) clearInterval(pollTimer);
      if (config.sessionId) pollTimer = setInterval(syncStatus, config.pollMs);
      if (config.autoTrack) attachAutoTrack();
      return module_exports();
    },

    emit: emit,

    decision: function (reason, options) {
      options = options || {};
      return emit(options.type || "decision", {
        action: options.action || "decision",
        decision: options.decision || null,
        reason: reason || null,
        guardrails: options.guardrails || [],
      });
    },

    pause: function () {
      remoteStatus = "paused";
      return postAction("/pause");
    },

    resume: function () {
      remoteStatus = "capturing";
      return postAction("/resume");
    },

    offRecord: function () {
      remoteStatus = "off_record";
      return postAction("/off-record");
    },

    start: function () {
      remoteStatus = "capturing";
      return postAction("/start");
    },

    finish: function () {
      remoteStatus = "finished";
      return postAction("/finish");
    },

    status: function () {
      return remoteStatus;
    },
  };

  function postAction(path) {
    if (!config.sessionId) return Promise.resolve(null);
    return fetch(endpoint(path), { method: "POST" })
      .then(function (res) {
        return res.ok ? res.json() : null;
      })
      .then(function (body) {
        if (body && body.status) remoteStatus = body.status;
        return body;
      })
      .catch(function () {
        return null;
      });
  }

  function module_exports() {
    return {
      sessionId: config.sessionId,
      status: remoteStatus,
      emit: emit,
    };
  }

  AIApprentice.__exports = module_exports;
  Object.defineProperty(AIApprentice, "config", {
    get: function () {
      return Object.assign({}, config);
    },
  });

  global.AIApprentice = AIApprentice;

  autoInitFromScript();
  bootstrap();

  function autoInitFromScript() {
    var script =
      document.currentScript ||
      document.querySelector("script[data-session-id][src*='ai-apprentice-capture']");
    if (!script) return;
    var sessionId = script.getAttribute("data-session-id");
    if (!sessionId) return;
    AIApprentice.init({
      apiUrl: script.getAttribute("data-api-url") || config.apiUrl,
      sessionId: sessionId,
      source: script.getAttribute("data-source") || config.source,
      autoTrack: script.getAttribute("data-auto-track") !== "false",
    });
  }

  function bootstrap() {
    if (!config.sessionId) return;
    syncStatus();
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(syncStatus, config.pollMs);
    if (config.autoTrack) attachAutoTrack();
  }
})(typeof window !== "undefined" ? window : this);
