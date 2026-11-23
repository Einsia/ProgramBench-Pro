CREATE TYPE season AS ENUM ('spring', 'summer', 'autumn', 'winter');

CREATE TABLE beds (
  id SERIAL PRIMARY KEY,
  label VARCHAR(30) NOT NULL UNIQUE,
  sunny BOOLEAN DEFAULT true
);

CREATE TABLE plants (
  id SERIAL PRIMARY KEY,
  bed_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  sown season,
  FOREIGN KEY (bed_id) REFERENCES beds (id) ON DELETE CASCADE
);

COMMENT ON TABLE plants IS 'what grows where';
