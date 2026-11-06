import { MEASURE_IDS } from '../src/measures.js';

// Workers KV, as far as this Worker uses it.
export class FakeKV {
  constructor() { this.map = new Map(); this.writes = 0; }
  async get(key) { return this.map.has(key) ? this.map.get(key) : null; }
  async put(key, value) {
    if (typeof value !== 'string') throw new TypeError('FakeKV stores strings only');
    this.writes++;
    this.map.set(key, value);
  }
  async delete(key) { this.writes++; this.map.delete(key); }
  json(key) { const v = this.map.get(key); return v === undefined ? undefined : JSON.parse(v); }
}

const FM = 'http://environment.data.gov.uk/flood-monitoring/id/measures/';
export const LISTED = MEASURE_IDS.slice(0, 3);
export const UNLISTED = ['ZZ999-level-stage-i-15_min-m', 'ZZ998-flow--i-15_min-m3_s'];

// The EA's latest-readings answer, in its own shape, with three of our measures and two others.
export function eaBody(extraItems = []) {
  const item = (id, i) => ({
    '@id': `http://environment.data.gov.uk/flood-monitoring/data/readings/${id}/2026-12-01T12-45-00Z`,
    dateTime: '2026-12-01T12:45:00Z', measure: FM + id, value: 0.1 + i,
  });
  return JSON.stringify({
    '@context': 'http://environment.data.gov.uk/flood-monitoring/meta/context.jsonld',
    meta: { publisher: 'Environment Agency', licence: 'http://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/', version: '0.9', comment: 'Status: Beta service', hasFormat: [] },
    items: [...LISTED, ...UNLISTED].map(item).concat(extraItems),
  });
}

const pad = (n) => String(n).padStart(2, '0');

// An S3 ListObjectsV2 answer as the radar bucket gives it: 96 composites a day, at :00, :15, :30 and :45,
// plus one file that is not a composite.
export function listingBody(date, { truncated = false, every = 15 } = {}) {
  const [y, m, d] = date.split('-');
  let contents = '';
  const one = (key, i) => `<Contents><Key>${key}</Key><LastModified>${date}T${pad(i % 24)}:0${i % 10}:12.000Z</LastModified>`
    + `<ETag>&quot;${(0xabc000 + i).toString(16)}e5f0c2d1a9b8&quot;</ETag><ChecksumAlgorithm>CRC64NVME</ChecksumAlgorithm>`
    + `<ChecksumType>FULL_OBJECT</ChecksumType><Size>${500000 + i}</Size><StorageClass>STANDARD</StorageClass></Contents>`;
  let i = 0;
  for (let h = 0; h < 24; h++) {
    for (let mi = 0; mi < 60; mi += every) {
      contents += one(`radar/${y}/${m}/${d}/${y}${m}${d}${pad(h)}${pad(mi)}_ODIM_ng_radar_rainrate_composite_1km_UK.h5`, i++);
    }
  }
  contents += one(`radar/${y}/${m}/${d}/README.txt`, i++);
  return '<?xml version="1.0" encoding="UTF-8"?>\n'
    + '<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/"><Name>met-office-radar-obs-data</Name>'
    + `<Prefix>radar/${y}/${m}/${d}/</Prefix><KeyCount>${i}</KeyCount><MaxKeys>1000</MaxKeys>`
    + `<IsTruncated>${truncated}</IsTruncated>${contents}</ListBucketResult>`;
}

// A network that answers the EA and the bucket, records every request, and can be told to misbehave.
export function makeNet(over = {}) {
  const calls = [];
  const fetch = async (url, init) => {
    calls.push({ url, init });
    const u = new URL(url);
    if (over[u.hostname]) return over[u.hostname](url, init);
    if (u.hostname === 'environment.data.gov.uk') return new Response(eaBody(), { status: 200, headers: { 'content-type': 'application/json' } });
    if (u.hostname === 'met-office-radar-obs-data.s3.amazonaws.com') {
      const p = u.searchParams.get('prefix').split('/');
      return new Response(listingBody(`${p[1]}-${p[2]}-${p[3]}`), { status: 200, headers: { 'content-type': 'application/xml' } });
    }
    throw new Error(`unexpected host ${u.hostname}`);
  };
  return { fetch, calls };
}

// A fetch that never answers until its signal fires, as a hung connection.
export const hang = (url, init) => new Promise((_, reject) => {
  init.signal.addEventListener('abort', () => reject(init.signal.reason));
});
