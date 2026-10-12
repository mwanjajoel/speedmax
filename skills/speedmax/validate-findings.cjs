#!/usr/bin/env node
'use strict';

// Validates speedmax findings.json (and optionally ledger.json).
// Zero dependencies. Usage:
//   node validate-findings.cjs <findings.json> [ledger.json]
// Exits 0 when valid, 1 with one error per line otherwise.

const fs = require('node:fs');
const path = require('node:path');

const SCHEMA = JSON.parse(fs.readFileSync(path.join(__dirname, 'findings-schema.json'), 'utf8'));
const CHECK_IDS = SCHEMA.items.properties.check_id.enum;
const LEDGER_STATUSES = ['applicable', 'not_applicable', 'blocked'];

// Input-derived strings are JSON-encoded in messages so they cannot add lines or terminal control sequences.
function show(value) {
  return JSON.stringify(value);
}

function typeOf(value) {
  if (value === null) return 'null';
  if (Array.isArray(value)) return 'array';
  if (Number.isInteger(value)) return 'integer';
  return typeof value;
}

function matchesType(value, expected) {
  const types = Array.isArray(expected) ? expected : [expected];
  const actual = typeOf(value);
  return types.some((t) => t === actual || (t === 'number' && actual === 'integer'));
}

// Interprets the subset of JSON Schema used by findings-schema.json.
function checkSchema(value, schema, where, errors) {
  if (schema.type && !matchesType(value, schema.type)) {
    errors.push(`${where}: expected ${[].concat(schema.type).join(' or ')}, got ${typeOf(value)}`);
    return;
  }
  if (schema.enum && !schema.enum.includes(value)) {
    errors.push(`${where}: ${JSON.stringify(value)} is not one of ${schema.enum.join(', ')}`);
  }
  if (typeof value === 'string') {
    if (schema.minLength && value.trim().length < schema.minLength) errors.push(`${where}: must not be empty`);
    if (schema.pattern && !new RegExp(schema.pattern).test(value)) errors.push(`${where}: ${JSON.stringify(value)} does not match ${schema.pattern}`);
  }
  if (Array.isArray(value) && schema.items) {
    value.forEach((item, i) => checkSchema(item, schema.items, `${where}[${i}]`, errors));
  }
  if (typeOf(value) === 'object') {
    for (const key of schema.required || []) {
      if (!(key in value)) errors.push(`${where}: missing required field "${key}"`);
    }
    for (const [key, sub] of Object.entries(schema.properties || {})) {
      if (key in value) checkSchema(value[key], sub, `${where}.${key}`, errors);
    }
  }
}

function validateFindings(findings, ledger) {
  const errors = [];
  checkSchema(findings, SCHEMA, 'findings', errors);
  if (!Array.isArray(findings)) return errors;

  const seen = new Set();
  findings.forEach((f, i) => {
    if (typeOf(f) !== 'object') return;
    const where = `findings[${i}]${f.id ? ` (${show(f.id)})` : ''}`;

    if (f.id) {
      if (seen.has(f.id)) errors.push(`${where}: duplicate id`);
      seen.add(f.id);
    }

    if (f.verdict === 'confirmed') {
      for (const key of ['impact', 'effort', 'evidence', 'fix']) {
        if (!(key in f)) errors.push(`${where}: confirmed finding requires "${key}"`);
      }
      if (!f.locations || f.locations.length === 0) errors.push(`${where}: confirmed finding requires at least one location`);
      if (f.evidence && f.evidence.baseline == null && !f.evidence.estimate) {
        errors.push(`${where}: evidence needs a numeric baseline or an estimate`);
      }
    } else {
      if ('impact' in f) errors.push(`${where}: only confirmed findings may have impact`);
      if (['approved', 'applied', 'verified'].includes(f.status)) {
        errors.push(`${where}: only confirmed findings may be ${f.status}`);
      }
    }
    if (f.verdict === 'needs_measurement' && !f.missing) {
      errors.push(`${where}: needs_measurement requires "missing" (the fact that would decide it)`);
    }

    if (f.status === 'verified' || f.status === 'reverted') {
      if (!f.after) {
        errors.push(`${where}: ${f.status} requires "after"`);
      } else if (f.evidence && f.after.metric !== f.evidence.metric) {
        errors.push(`${where}: after.metric ${show(f.after.metric)} must match evidence.metric ${show(f.evidence.metric)}`);
      }
    }

    if (ledger && ledger.checks && ledger.checks[f.check_id] && ledger.checks[f.check_id].status === 'not_applicable' && f.verdict !== 'not_applicable') {
      errors.push(`${where}: check ${show(f.check_id)} is not_applicable in the ledger`);
    }
  });

  if (ledger) errors.push(...validateLedger(ledger));
  return errors;
}

function validateLedger(ledger) {
  const errors = [];
  if (typeOf(ledger) !== 'object' || typeOf(ledger.checks) !== 'object') {
    return ['ledger: expected an object with a "checks" object'];
  }
  for (const id of CHECK_IDS) {
    const entry = ledger.checks[id];
    if (!entry) {
      errors.push(`ledger: missing check ${id}`);
      continue;
    }
    if (!LEDGER_STATUSES.includes(entry.status)) errors.push(`ledger.${id}: status must be one of ${LEDGER_STATUSES.join(', ')}`);
    if (typeof entry.reason !== 'string' || entry.reason.trim() === '') errors.push(`ledger.${id}: reason is required`);
  }
  for (const id of Object.keys(ledger.checks)) {
    if (!CHECK_IDS.includes(id)) errors.push(`ledger: unknown check ${show(id)}`);
  }
  return errors;
}

module.exports = { validateFindings, validateLedger, CHECK_IDS };

if (require.main === module) {
  const [findingsPath, ledgerPath] = process.argv.slice(2);
  if (!findingsPath) {
    console.error('usage: node validate-findings.cjs <findings.json> [ledger.json]');
    process.exit(2);
  }
  const read = (p) => JSON.parse(fs.readFileSync(p, 'utf8'));
  let errors;
  try {
    errors = validateFindings(read(findingsPath), ledgerPath ? read(ledgerPath) : undefined);
  } catch (err) {
    errors = [`could not read input: ${show(err.message)}`];
  }
  if (errors.length) {
    errors.forEach((e) => console.error(e));
    process.exit(1);
  }
  console.log('findings valid');
}
