/**
 * crop-utils.js — small, testable helpers used across the SproutScan UI.
 *
 * Extracted from inline <script> blocks so the logic can be unit-tested
 * without a browser. Loads in the browser (window.CropUtils) and in
 * Node/CommonJS tests (module.exports).
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.CropUtils = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /**
   * Map an AI confidence percentage to a human status label.
   * Mirrors the backend rule in app.read_latest_logs_by_crop.
   */
  function cropStatus(confidence) {
    if (typeof confidence !== "number" || Number.isNaN(confidence)) {
      return "Unknown";
    }
    return confidence >= 90 ? "Normal" : "Needs to be checked";
  }

  /**
   * Case-insensitive filter of a list of rows by one or more fields.
   * Returns a new array; original is untouched.
   */
  function filterRows(rows, query, fields) {
    const q = String(query || "").trim().toLowerCase();
    if (!q) return rows.slice();
    return rows.filter(function (row) {
      return fields.some(function (field) {
        const value = row[field];
        if (value == null) return false;
        return String(value).toLowerCase().includes(q);
      });
    });
  }

  /** Escape HTML in user-supplied text before inserting into the DOM. */
  function escapeHtml(text) {
    return String(text == null ? "" : text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  return {
    cropStatus: cropStatus,
    filterRows: filterRows,
    escapeHtml: escapeHtml,
  };
});