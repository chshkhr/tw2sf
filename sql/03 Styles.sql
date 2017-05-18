CREATE TABLE IF NOT EXISTS Styles (
  StyleId VARCHAR(50) NOT NULL,
  ProductID BIGINT NOT NULL,
  PRIMARY KEY (StyleId)
) DEFAULT CHARSET=utf8 COLLATE=utf8_bin;

CREATE INDEX ixStyles_StyleId ON Styles(StyleId);

