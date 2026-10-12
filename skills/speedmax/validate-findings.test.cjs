'use strict';

const test = require('node:test');
const assert = require('node:assert');
const { validateFindings, validateLedger, CHECK_IDS } = require('./validate-findings.cjs');

function confirmed(overrides = {}) {
  return {
    id: 'F-001',
    check_id: 'IMG-02',
    title: 'Hero image is lazy-loaded',
    verdict: 'confirmed',
    impact: 'high',
    effort: 'S',
    locations: ['app/page.tsx:14'],
    evidence: { tool: 'lighthouse', metric: 'lcp_ms', baseline: 4810, unit: 'ms', runs: 5 },
    fix: { summary: 'Add priority to the hero image', files: ['app/page.tsx'] },
    status: 'proposed',
    ...overrides,
  };
}

function needsMeasurement(overrides = {}) {
  return {
    id: 'F-002',
    check_id: 'INFRA-02',
    title: 'Possible cold start',
    verdict: 'needs_measurement',
    missing: 'first-request latency after idle',
    status: 'proposed',
    ...overrides,
  };
}

function fullLedger(overrides = {}) {
  const checks = Object.fromEntries(CHECK_IDS.map((id) => [id, { status: 'applicable', reason: 'present' }]));
  return { checks: { ...checks, ...overrides } };
}

test('valid findings and ledger pass', () => {
  assert.deepStrictEqual(validateFindings([confirmed(), needsMeasurement()], fullLedger()), []);
});

test('empty findings array is valid', () => {
  assert.deepStrictEqual(validateFindings([]), []);
});

test('rejects a non-array', () => {
  assert.ok(validateFindings({}).length > 0);
});

test('rejects unknown check id', () => {
  const errors = validateFindings([confirmed({ check_id: 'SEO-01' })]);
  assert.ok(errors.some((e) => e.includes('check_id')));
});

test('rejects bad id format and duplicates', () => {
  assert.ok(validateFindings([confirmed({ id: '1' })]).some((e) => e.includes('.id')));
  assert.ok(validateFindings([confirmed(), confirmed()]).some((e) => e.includes('duplicate')));
});

test('confirmed requires impact, effort, evidence, fix, and a location', () => {
  const { impact, effort, evidence, fix, ...bare } = confirmed();
  const errors = validateFindings([{ ...bare, locations: [] }]);
  for (const key of ['impact', 'effort', 'evidence', 'fix', 'location']) {
    assert.ok(errors.some((e) => e.includes(key)), `expected error about ${key}`);
  }
});

test('confirmed evidence needs a baseline or an estimate', () => {
  const noNumber = confirmed({ evidence: { tool: 'source', metric: 'queries_per_request', baseline: null } });
  assert.ok(validateFindings([noNumber]).some((e) => e.includes('estimate')));
  const withEstimate = confirmed({ evidence: { tool: 'source', metric: 'queries_per_request', baseline: null, estimate: 'N+1 for N rows' } });
  assert.deepStrictEqual(validateFindings([withEstimate]), []);
});

test('needs_measurement must not have impact and must name the missing fact', () => {
  const errors = validateFindings([needsMeasurement({ impact: 'high', missing: undefined })]);
  assert.ok(errors.some((e) => e.includes('only confirmed findings may have impact')));
  assert.ok(errors.some((e) => e.includes('missing')));
});

test('unconfirmed findings cannot be approved', () => {
  assert.ok(validateFindings([needsMeasurement({ status: 'approved' })]).some((e) => e.includes('approved')));
});

test('verified requires after with matching metric', () => {
  assert.ok(validateFindings([confirmed({ status: 'verified' })]).some((e) => e.includes('after')));
  assert.ok(validateFindings([confirmed({ status: 'verified', after: { metric: 'tbt_ms', value: 100 } })]).some((e) => e.includes('must match')));
  assert.deepStrictEqual(validateFindings([confirmed({ status: 'verified', after: { metric: 'lcp_ms', value: 2300 } })]), []);
});

test('ledger must list every check with a status and reason', () => {
  const ledger = fullLedger();
  delete ledger.checks['DB-01'];
  ledger.checks['UX-01'] = { status: 'maybe', reason: '' };
  const errors = validateLedger(ledger);
  assert.ok(errors.some((e) => e.includes('missing check DB-01')));
  assert.ok(errors.some((e) => e.includes('UX-01: status')));
  assert.ok(errors.some((e) => e.includes('UX-01: reason')));
});

test('finding on a not_applicable check is rejected', () => {
  const ledger = fullLedger({ 'IMG-02': { status: 'not_applicable', reason: 'no images' } });
  assert.ok(validateFindings([confirmed()], ledger).some((e) => e.includes('not_applicable in the ledger')));
});
