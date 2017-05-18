CREATE TABLE IF NOT EXISTS Items (
  ItemId VARCHAR(50) NOT NULL,
  StyleId VARCHAR(50) NOT NULL,
  VariantID BIGINT NOT NULL,
  PRIMARY KEY (ItemId),
  FOREIGN KEY fkItems_Styles(StyleId) REFERENCES Styles(StyleId) ON DELETE CASCADE
) DEFAULT CHARSET=utf8 COLLATE=utf8_bin;

