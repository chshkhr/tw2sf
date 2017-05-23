CREATE TABLE IF NOT EXISTS Items (
  ItemId VARCHAR(50) NOT NULL,
  StyleId VARCHAR(50),
  VariantID BIGINT,
  Qty NUMERIC(15,4) NULL,  #  Qty - CommittedQty - DamagedQty
  LocCount INT,
  QtySent TIMESTAMP(3) NULL,
  QtyApiRequestTime TIMESTAMP(3) NULL,
  PRIMARY KEY (ItemId),
  FOREIGN KEY fkItems_Styles(StyleId) REFERENCES Styles(StyleId) ON DELETE CASCADE
) DEFAULT CHARSET=utf8 COLLATE=utf8_bin;

CREATE INDEX ixItems_QtyApiRequestTime ON Items(QtyApiRequestTime);

CREATE INDEX ixItems_QtySent ON Items(QtySent);

CREATE TRIGGER trbuItems_Qty
BEFORE UPDATE ON Items
FOR EACH ROW
BEGIN
  IF COALESCE(NEW.Qty,0)<>COALESCE(OLD.Qty,0) THEN
    SET NEW.QtySent = NULL;
  END IF;
END;

