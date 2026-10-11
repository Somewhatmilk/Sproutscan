/**
 * crop-utils.test.js — unit tests for static/js/crop-utils.js
 *
 * Run:  node --test tests/
 */
const test = require("node:test");
const assert = require("node:assert");
const CropUtils = require("../static/js/crop-utils.js");

test("cropStatus: 90+ is Normal", () => {
  assert.strictEqual(CropUtils.cropStatus(90), "Normal");
  assert.strictEqual(CropUtils.cropStatus(100), "Normal");
  assert.strictEqual(CropUtils.cropStatus(99.9), "Normal");
});

test("cropStatus: below 90 needs checking", () => {
  assert.strictEqual(CropUtils.cropStatus(89), "Needs to be checked");
  assert.strictEqual(CropUtils.cropStatus(0), "Needs to be checked");
});

test("cropStatus: non-numeric input is Unknown", () => {
  assert.strictEqual(CropUtils.cropStatus(null), "Unknown");
  assert.strictEqual(CropUtils.cropStatus(undefined), "Unknown");
  assert.strictEqual(CropUtils.cropStatus("high"), "Unknown");
  assert.strictEqual(CropUtils.cropStatus(NaN), "Unknown");
});

test("filterRows: empty query returns all rows unchanged", () => {
  const rows = [{ name: "Tomato" }, { name: "Chili" }];
  const out = CropUtils.filterRows(rows, "", ["name"]);
  assert.strictEqual(out.length, 2);
  assert.notStrictEqual(out, rows, "should return a copy");
});

test("filterRows: matches case-insensitively across fields", () => {
  const rows = [
    { name: "Tomato", zone: "A1" },
    { name: "Chili", zone: "B2" },
  ];
  assert.strictEqual(CropUtils.filterRows(rows, "tomato", ["name"]).length, 1);
  assert.strictEqual(CropUtils.filterRows(rows, "b2", ["name", "zone"]).length, 1);
});

test("filterRows: null field values do not crash", () => {
  const rows = [{ name: "Tomato", zone: null }];
  assert.strictEqual(CropUtils.filterRows(rows, "tomato", ["zone"]).length, 0);
});

test("escapeHtml neutralizes markup", () => {
  const out = CropUtils.escapeHtml('<img src=x onerror="alert(1)">');
  assert.ok(!out.includes("<img"));
  assert.ok(!out.includes('"'));
  assert.ok(out.includes("&lt;img"));
  assert.ok(out.includes("&quot;"));
});

test("escapeHtml handles null/undefined", () => {
  assert.strictEqual(CropUtils.escapeHtml(null), "");
  assert.strictEqual(CropUtils.escapeHtml(undefined), "");
});