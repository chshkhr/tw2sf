CREATE TABLE IF NOT EXISTS StyleStream (
  ID INT NOT NULL AUTO_INCREMENT,
  SyncRunsID INT NOT NULL,
  InsDateTime TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  StyleNo VARCHAR(50) NOT NULL,
  StyleId VARCHAR(50),
  RecModified TIMESTAMP(3) NOT NULL,
  Title VARCHAR(255),
  StyleXml LONGTEXT NOT NULL,
  ProductID BIGINT, # If ProductID is not null - Product sent successfully
  ProductSent TIMESTAMP(3) NULL, # Clean it to ReSend this Style (modify StyleXml if need)
  OldProductID BIGINT, # Null - New, OldProductID=ProductID - Updated, OldProductID<>ProductID - ReCreated
  VariantsCount INT,
  ErrMes TEXT,  # Null if the product sent successfully
  ErrCode INT DEFAULT 0,  # -4 total style qty equals zero while PUBLISH_ZERO_QTY=False
                          # -3 Style belongs to inactive Channel
                          # -2 Style Version is Obsolete
                          # -1 Exception
                          # >200 - API err https://help.shopify.com/api/getting-started/response-status-codes
  RetryCount INT DEFAULT 0,
  PRIMARY KEY (ID),
  FOREIGN KEY fkStyleStream_SyncRuns(SyncRunsID) REFERENCES SyncRuns(ID) ON DELETE CASCADE
) DEFAULT CHARSET=utf8 COLLATE=utf8_bin
AUTO_INCREMENT=1;

# max(RecModified)
CREATE INDEX ixStyleStream_RecModified ON StyleStream(RecModified);

# find not sent and resend with modified StyleXml:
# ProductID is null and ProductSent is null
CREATE INDEX ixStyleStream_Product ON StyleStream(ProductID, ProductSent);

# select count(*) ... group by StyleNo
CREATE INDEX ixStyleStream_StyleNo ON StyleStream(StyleNo);

# select * ... where ErrCode=429
CREATE INDEX ixStyleStream_ErrCode ON StyleStream(ErrCode);

CREATE TRIGGER traiStyleStream_ProductID
AFTER INSERT ON StyleStream
FOR EACH ROW
BEGIN
  IF NEW.StyleId IS NOT NULL THEN
    INSERT INTO Styles (StyleId,ProductID) VALUES (NEW.StyleId,NEW.ProductID)
    ON DUPLICATE KEY UPDATE ProductID = NEW.ProductID;
    #UPDATE Items SET Qty = NULL WHERE StyleID = NEW.StyleId;
  END IF;
END;

CREATE TRIGGER trauStyleStream_ProductID
AFTER UPDATE ON StyleStream
FOR EACH ROW
BEGIN
  IF NEW.StyleId IS NOT NULL THEN
    INSERT INTO Styles (StyleId,ProductID) VALUES (NEW.StyleId,NEW.ProductID)
    ON DUPLICATE KEY UPDATE ProductID = NEW.ProductID;
    #UPDATE Items SET Qty = NULL WHERE StyleID = NEW.StyleId;
  END IF;
END;




