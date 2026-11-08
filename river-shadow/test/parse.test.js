import { test } from 'node:test';
import assert from 'node:assert/strict';
import { filterReadings, inWindow, parseListing } from '../src/index.js';
import { MEASURE_IDS } from '../src/measures.js';
import { eaBody, listingBody } from './helpers.js';

// As S3 answers: a namespace, entities in ETag, fields in its own order, whitespace between elements.
const SAMPLE = `<?xml version="1.0" encoding="UTF-8"?>
<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
  <Name>met-office-radar-obs-data</Name><Prefix>radar/2026/11/05/</Prefix><KeyCount>2</KeyCount><MaxKeys>1000</MaxKeys>
  <IsTruncated>true</IsTruncated><NextContinuationToken>1abc==</NextContinuationToken>
  <Contents>
    <Key>radar/2026/11/05/202611051200_ODIM_ng_radar_rainrate_composite_1km_UK.h5</Key>
    <LastModified>2026-11-05T12:08:41.000Z</LastModified>
    <ETag>&quot;9b2cf535f27731c974343645a3985328&quot;</ETag>
    <ChecksumAlgorithm>CRC64NVME</ChecksumAlgorithm><ChecksumType>FULL_OBJECT</ChecksumType>
    <Size>402113</Size><StorageClass>STANDARD</StorageClass>
  </Contents>
  <Contents>
    <Key>radar/2026/11/05/202611051215_ODIM_ng_radar_rainrate_composite_1km_UK.h5</Key>
    <LastModified>2026-11-05T12:23:40.000Z</LastModified>
    <ETag>&quot;6d1f-2&quot;</ETag>
    <Size>398650</Size><StorageClass>STANDARD</StorageClass>
  </Contents>
</ListBucketResult>`;

test('parseListing reads a realistic S3 answer', () => {
  const { contents, truncated } = parseListing(SAMPLE);
  assert.equal(truncated, true);
  assert.deepEqual(contents, [
    { key: 'radar/2026/11/05/202611051200_ODIM_ng_radar_rainrate_composite_1km_UK.h5', size: 402113, last_modified: '2026-11-05T12:08:41.000Z', etag: '"9b2cf535f27731c974343645a3985328"' },
    { key: 'radar/2026/11/05/202611051215_ODIM_ng_radar_rainrate_composite_1km_UK.h5', size: 398650, last_modified: '2026-11-05T12:23:40.000Z', etag: '"6d1f-2"' },
  ]);
  assert.equal(parseListing(listingBody('2026-12-01')).contents.length, 97);
  assert.equal(parseListing(listingBody('2026-12-01')).truncated, false);
  assert.deepEqual(parseListing('<?xml version="1.0"?><ListBucketResult xmlns="x"><KeyCount>0</KeyCount><IsTruncated>false</IsTruncated></ListBucketResult>').contents, []);
  assert.throws(() => parseListing('<Error><Code>AccessDenied</Code></Error>'), /not a ListBucketResult/);
});

test('inWindow keeps (issue - 3 h, issue] and only composite names', () => {
  const { contents } = parseListing(listingBody('2026-12-01', { every: 5 }));
  const keys = inWindow(contents, Date.parse('2026-12-01T13:00:00Z')).map((c) => c.key.slice(17, 29));
  assert.equal(keys.length, 36);
  assert.equal(keys[0], '202612011005');   // 10:00 itself is out
  assert.equal(keys.at(-1), '202612011300');  // 13:00 itself is in
  assert.ok(!keys.some((k) => k > '202612011300'));
});

test('filterReadings keeps listed measures only, by id, whatever the scheme', () => {
  const extra = [
    { measure: `https://environment.data.gov.uk/flood-monitoring/id/measures/${MEASURE_IDS[5]}`, dateTime: '2026-12-01T12:30:00Z', value: [0.2, 0.3] },
    { measure: null, value: 1 }, null, 'x',
  ];
  const { total, items } = filterReadings(eaBody(extra));
  assert.equal(total, 9);
  assert.equal(items.length, 4);
  assert.deepEqual(items[3], { measure: extra[0].measure, dateTime: '2026-12-01T12:30:00Z', value: [0.2, 0.3] });
  assert.throws(() => filterReadings('{"meta":{}}'), /no items list/);
});
