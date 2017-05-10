CREATE TABLE IF NOT EXISTS SyncRuns (
  ID INT NOT NULL AUTO_INCREMENT,
  StartTime TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),  # time of the first request
  # Teamworker fields
  SessionNum INT DEFAULT 0,  # number of current session (one ID can have multiple sessions)
  SessionStartTime TIMESTAMP(3) NULL,  # last response time
  ApiDocumentId VARCHAR(50),  # f.e. 345A06F1-1B64-4CB5-9075-8ED783047B7A
  ChunkCount INT DEFAULT 0,  # number of chunks with at least one style inside
  LastChunkTime TIMESTAMP(3) NULL,  # arrival time of chunk with at least one style inside
  StylesFound INT DEFAULT 0,
  SessionFinishTime TIMESTAMP(3) NULL,  # if an old record has SrcFinishTime=Null then interruption took place here
  # Shopifier fields
  DstLastSendTime TIMESTAMP(3) NULL,
  DstProcessedEntities INT DEFAULT 0,
  DstErrorCount INT DEFAULT 0,
  PRIMARY KEY (ID)
) DEFAULT CHARSET=utf8 COLLATE=utf8_bin
AUTO_INCREMENT=1;

# max(SessionStartTime) - check if teamworker thread is alive
CREATE INDEX ixSyncRuns_SessionStartTime ON SyncRuns(SessionStartTime);

# max(DstLastSendTime) - check if shopifier thread is alive
CREATE INDEX ixSyncRuns_DstLastSendTime ON SyncRuns(DstLastSendTime);
