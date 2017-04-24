CREATE TABLE IF NOT EXISTS SyncRuns (
  ID INT NOT NULL AUTO_INCREMENT,
  StartDateTime TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3), # время начала синхронизации
  ApiDocumentId VARCHAR(50), # f.e. 345A06F1-1B64-4CB5-9075-8ED783047B7A
  StylesFound INT DEFAULT 0,
  ChunkCount INT DEFAULT 0,
  LastChunkTime TIMESTAMP(3) NULL,
  LastUpdateDateTime TIMESTAMP(3) NULL, # время последнего обновления данных по этой синхронизации
  ProcessedEntities INT DEFAULT 0, # количество обработанных сущностей
  ErrCount INT DEFAULT 0,
  #LastRecModified TIMESTAMP(3) NULL, # ?
  #Status SMALLINT DEFAULT NULL,# Null - Not Started, 0 – Running, 1 – Success, 2 – Error, 3 – InterruptedByTimer
  #EndDateTime TIMESTAMP(3) NULL, # время окончания
PRIMARY KEY (ID)
) DEFAULT CHARSET=utf8 COLLATE=utf8_bin
AUTO_INCREMENT=1;

# max(LastChunkTime) - check if teamworker thread is alive
CREATE INDEX ixSyncRuns_LastChunkTime ON SyncRuns(LastChunkTime);

# max(LastUpdateDateTime) - check if shopifier thread is alive
CREATE INDEX ixSyncRuns_LastUpdateDateTime ON SyncRuns(LastUpdateDateTime);
