-- Reserve photo space before writing KV. Keep the reservation until every photo is deleted,
-- including when an upload or deletion fails. The daily cleanup retries abandoned uploads.
CREATE TABLE photo_storage (
  id TEXT PRIMARY KEY,
  photos INTEGER NOT NULL CHECK (photos BETWEEN 1 AND 3),
  bytes INTEGER NOT NULL CHECK (bytes >= 0),
  created_at TEXT NOT NULL,
  deleting INTEGER NOT NULL DEFAULT 0 CHECK (deleting IN (0, 1)),
  estimated INTEGER NOT NULL DEFAULT 0 CHECK (estimated IN (0, 1))
);

-- Older reviews recorded dimensions but not byte sizes. Reserve the largest allowed size
-- for those photos, rather than treating them as free space. New uploads use actual sizes.
INSERT INTO photo_storage (id, photos, bytes, created_at, estimated)
SELECT id, json_array_length(photos), json_array_length(photos) * (1536 + 200) * 1024, created_at, 1
FROM reviews WHERE json_array_length(photos) > 0;
