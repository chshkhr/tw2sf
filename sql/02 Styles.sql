CREATE TABLE IF NOT EXISTS Styles (
  ID INT NOT NULL AUTO_INCREMENT,
  SyncRunsID INT NOT NULL,
  InsDateTime TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  StyleNo BIGINT NOT NULL,
  RecModified TIMESTAMP(3) NOT NULL,
  Title varchar(255),
  StyleXml LONGTEXT NOT NULL,
  ProductID BIGINT, # If ProductID is not null - Product sent successfully
  ProductSent TIMESTAMP(3) NULL, # Clean it to ReSend this Style (modify StyleXml if need)
  OldProductID BIGINT, # Null - New, OldProductID=ProductID - Updated, OldProductID<>ProductID - ReCreated
  VariantsCount INT,
  ErrMes TEXT,  # Null if the product sent successfully
  ErrCode INT DEFAULT 0,  # -1 - Exception, >200 https://help.shopify.com/api/getting-started/response-status-codes
  RetryCount INT DEFAULT 0,
  PRIMARY KEY (ID),
  FOREIGN KEY fkSyncRuns(SyncRunsID) REFERENCES SyncRuns(ID) ON DELETE CASCADE
) DEFAULT CHARSET=utf8 COLLATE=utf8_bin
AUTO_INCREMENT=1;

# max(RecModified)
CREATE INDEX ixStyles_RecModified ON Styles(RecModified);

# find not sent and resend modified via StyleXml:
# ProductID is null and ProductSent is null
CREATE INDEX ixStyles_Product ON Styles(ProductID, ProductSent);

# select count(*) ... group by StyleNo
CREATE INDEX ixStyles_StyleNo ON Styles(StyleNo);

# select * ... where ErrCode=429
CREATE INDEX ixStyles_ErrCode ON Styles(ErrCode);



