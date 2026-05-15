"use strict";

const PLUGIN_ID = "zotero-auto-pdf-fetch@epi-opto-mentor";
const PREF_PREFIX = "extensions.zotero-auto-pdf-fetch.";

var AutoPDFFetch = {
  observerID: null,
  pendingItemIDs: new Set(),
  timerID: null,
  running: false,

  observer: {
    notify: async function (event, type, ids, extraData) {
      await AutoPDFFetch.onNotify(event, type, ids, extraData);
    }
  },

  startup: function () {
    if (!this.getBoolPref("enabled", true)) {
      this.log("Plugin loaded but disabled by preference");
      return;
    }

    if (this.observerID) {
      return;
    }

    this.observerID = Zotero.Notifier.registerObserver(
      this.observer,
      ["item"],
      PLUGIN_ID
    );
    this.log("Registered item add observer");
  },

  shutdown: function () {
    this.clearTimer();
    this.pendingItemIDs.clear();

    if (this.observerID) {
      Zotero.Notifier.unregisterObserver(this.observerID);
      this.observerID = null;
      this.log("Unregistered item observer");
    }
  },

  onNotify: async function (event, type, ids) {
    if (event !== "add" || type !== "item") {
      return;
    }

    if (!this.getBoolPref("enabled", true)) {
      return;
    }

    ids = Array.isArray(ids) ? ids : [ids];
    for (let id of ids) {
      if (id) {
        this.pendingItemIDs.add(id);
      }
    }

    this.schedule();
  },

  schedule: function () {
    if (this.timerID) {
      return;
    }

    let delay = this.getIntPref("delayMS", 20000, 1000, 300000);
    this.timerID = setTimeout(async () => {
      this.timerID = null;
      await this.processPending();
    }, delay);
  },

  processPending: async function () {
    if (this.running) {
      this.schedule();
      return;
    }

    let ids = Array.from(this.pendingItemIDs);
    if (!ids.length) {
      return;
    }

    this.pendingItemIDs.clear();

    let maxBatchSize = this.getIntPref("maxBatchSize", 25, 1, 500);
    let batchIDs = ids.slice(0, maxBatchSize);
    for (let id of ids.slice(maxBatchSize)) {
      this.pendingItemIDs.add(id);
    }

    this.running = true;
    try {
      let items = Zotero.Items.get(batchIDs).filter(item => this.shouldProcessItem(item));
      if (!items.length) {
        this.log("No eligible new items in batch");
        return;
      }

      let methods = this.getMethods();
      let sameDomainRequestDelay = this.getIntPref(
        "sameDomainRequestDelayMS",
        1000,
        0,
        600000
      );

      this.log(`Looking for available files for ${items.length} new item(s) via ${methods.join(",")}`);
      await Zotero.Attachments.addAvailableFiles(items, {
        methods,
        sameDomainRequestDelay
      });
    }
    catch (e) {
      Zotero.logError(e);
    }
    finally {
      this.running = false;
      if (this.pendingItemIDs.size) {
        this.schedule();
      }
    }
  },

  shouldProcessItem: function (item) {
    try {
      if (!item || !item.id) {
        return false;
      }
      if (!item.isRegularItem || !item.isRegularItem()) {
        return false;
      }
      if (item.deleted || item.isFeedItem) {
        return false;
      }

      let library = Zotero.Libraries.get(item.libraryID);
      if (library && library.filesEditable === false) {
        this.log(`Skipping item ${item.key}: files are not editable in this library`);
        return false;
      }

      return Zotero.Attachments.canFindFileForItem(item);
    }
    catch (e) {
      Zotero.logError(e);
      return false;
    }
  },

  getMethods: function () {
    let raw = this.getStringPref("methods", "doi,url,oa");
    let allowed = new Set(["doi", "url", "oa", "custom"]);
    let methods = raw
      .split(",")
      .map(s => s.trim().toLowerCase())
      .filter(s => allowed.has(s));

    if (!this.getBoolPref("includeCustomResolvers", false)) {
      methods = methods.filter(method => method !== "custom");
    }

    if (!methods.length) {
      methods = ["doi", "url", "oa"];
    }
    return methods;
  },

  getBoolPref: function (name, fallback) {
    try {
      return Services.prefs.getBoolPref(PREF_PREFIX + name);
    }
    catch (e) {
      return fallback;
    }
  },

  getIntPref: function (name, fallback, min, max) {
    try {
      let value = Services.prefs.getIntPref(PREF_PREFIX + name);
      if (!Number.isFinite(value)) {
        return fallback;
      }
      return Math.max(min, Math.min(max, value));
    }
    catch (e) {
      return fallback;
    }
  },

  getStringPref: function (name, fallback) {
    try {
      return Services.prefs.getStringPref(PREF_PREFIX + name);
    }
    catch (e) {
      return fallback;
    }
  },

  clearTimer: function () {
    if (this.timerID) {
      clearTimeout(this.timerID);
      this.timerID = null;
    }
  },

  log: function (message) {
    Zotero.debug(`[Zotero Auto PDF Fetch] ${message}`, 3);
  }
};

function install(data, reason) {}

function startup(data, reason) {
  AutoPDFFetch.startup();
}

function shutdown(data, reason) {
  AutoPDFFetch.shutdown();
}

function uninstall(data, reason) {}
