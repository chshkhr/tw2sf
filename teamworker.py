import os
import glob
import argparse
import datetime
import dateutil.parser # sudo python3.6 -m pip install python-dateutil
import xml.etree.ElementTree as ET

import twmysql
import utils
from teamwork import Teamwork

# Teamwork constants
TW_API_KEY = '4f684ea6-f949-42d0-837b-7eaabf10ae03'  # '9CA9E29D-D258-48DC-886E-A507F55A03D6'
TW_URL = 'https://qa03chq.teamworkinsight.com/'  # 'https://hattestchq.teamworkinsight.com/'
TW_LOCATIONS = ['7A2151DB-EFC2-49BD-913B-66EEE0DF38C1',
                'CA2E5100-1853-419C-9661-F11D6CFC4FB1']  # for RTA
START_DATE = dateutil.parser.parse('2014-01-01 00:00:00')
_locs = '|'.join(TW_LOCATIONS)
_loc_count = len(TW_LOCATIONS)


class Teamwork2Shopify(Teamwork):
    def __init__(self, api_key=TW_API_KEY, url=TW_URL, start_date=START_DATE, shift_ms=3):
        super().__init__(api_key, url)
        # Settings
        self.start_date = start_date  # dateutil.parser.parse('2014-01-01 00:00:00')  # used on first run, get from DB later
        self.shift_ms = shift_ms  # 3  # set 3 at minimum to avoid repeatable sending of the last record
        self.syncRunsID = None
        self.db = None

    def _process_styles_xml(self, xml_root):
        # Proces XML from Teamwork and Save results to MySqL DB

        done = 0

        # Get syncRunsID of not finished session or create the new one
        if self.chunk_num == 1:  # means First Run
            with self.db.cursor() as cursor:
                cursor.execute('SELECT Max(ID) as SyncRunsID FROM SyncRuns')
                data = cursor.fetchone()
                self.syncRunsID = data['SyncRunsID']
                if self.syncRunsID is not None:
                    cursor.execute('SELECT StylesFound, SessionFinishTime FROM SyncRuns WHERE ID = %s',
                                   (self.syncRunsID,))
                    data = cursor.fetchone()
                if self.syncRunsID is None or data['StylesFound'] > 0 or data['SessionFinishTime'] is None:
                    # 'SessionFinishTime is Null' means simultaneous executions or interrupted process (we keep this info)
                    cursor.execute('INSERT INTO SyncRuns (ApiDocumentId) VALUES (Null)')
                    cursor.execute('SELECT LAST_INSERT_ID() as SyncRunsID')
                    data = cursor.fetchone()
                    self.syncRunsID = data['SyncRunsID']


        if xml_root and self.apiDocumentId:
            try:
                with self.db.cursor() as cursor:
                    # Write Starting Time on First run
                    if self.chunk_num == 1:
                        cursor.execute('SELECT Max(ID) as SyncRunsID FROM SyncRuns')
                        data = cursor.fetchone()
                        self.syncRunsID = data['SyncRunsID']
                        cursor.execute('UPDATE SyncRuns SET '
                                       'SessionNum = SessionNum + 1, '
                                       'ApiDocumentId = %s, ' 
                                       'SessionStartTime = CURRENT_TIMESTAMP(3), '
                                       'SessionFinishTime = Null '
                                       'WHERE ID = %s',
                                       (self.apiDocumentId,
                                        self.syncRunsID,))

                    # Copy Styles to Items
                    for style in xml_root.iter('Style'):
                        try:
                            styleno = style.find('StyleNo').text
                            title = (style.find('CustomText5').text or
                                     style.find('Description4').text or
                                     styleno)

                            self.start_date = style.find('RecModified').text  # next time we'll start from this date (next request)
                            styleid = style.find('StyleId').text
                            print('\t\t\t', self.skip+done+1, self.start_date, styleno, styleid, title)

                            cursor.execute('INSERT IGNORE INTO Styles (StyleId) '
                                           'VALUES (%s) ',
                                           (styleid,))

                            items = style.iter('Item')
                            var_count = 0
                            for item in items:
                                var_count += 1
                                cursor.execute('INSERT IGNORE INTO Items (ItemId, StyleId) '
                                               'VALUES (%s, %s) ',
                                               (item.find('ItemId').text,
                                                styleid,))

                            cursor.execute('INSERT INTO StyleStream '
                                           '(SyncRunsID, StyleNo, StyleId, RecModified, Title, '
                                           'VariantsCount, StyleXml) '
                                           'VALUES (%s, %s, %s, %s, %s, %s, %s)',
                                           (self.syncRunsID, styleno, styleid, self.start_date, title,
                                            var_count, ET.tostring(style), ))

                        except Exception as e:
                            print('\t\t\t\t', e)
                        finally:
                            done += 1

                    if done > 0:
                        print(f'\t\t\tStyles received: {done}. Saved to DB "{twmysql.HOST} {twmysql.DB}"')

                    # Write current time and counters on each run
                    cursor.execute('UPDATE SyncRuns SET '                      
                                   'SessionFinishTime = case when %s = 0 then CURRENT_TIMESTAMP(3) else SessionFinishTime end, '
                                   'StylesFound = StylesFound + %s, '
                                   'ChunkCount = ChunkCount + %s, '
                                   'LastChunkTime = case when %s > 0 then CURRENT_TIMESTAMP(3) else LastChunkTime end '
                                   'where ID = %s;',
                                   (int(done > 0),
                                    done,
                                    int(done > 0),
                                    done,
                                    self.syncRunsID,
                                    ))
            finally:
                if done:
                    self.save_last_response('-styles')
        return done

    def init_tw(self, drop=False):
        # prepare folders for log and xml
        utils.mkdirs(drop)

        # MySql Init
        self.db = twmysql.get_db()
        if not self.db:
            return False

        # if we want to start from scratch then we drop all of our tables
        if drop:
            with self.db.cursor() as cursor:
                for t in ['Items', 'Styles', 'StyleStream', 'SyncRuns']:
                    sql = f'DROP TABLE IF EXISTS {t};'
                    print('\t', sql)
                    cursor.execute(sql)

        # Execute SQL scripts from .\SQL folder (if SyncRuns table not found in DB)
        with self.db.cursor() as cursor:
            if drop or not cursor.execute("SHOW TABLES LIKE 'SyncRuns'"):
                for fn in sorted(glob.glob(os.path.join('sql', '*.sql'))):
                    print(f'\tExecuting {fn}...')
                    with open(fn,'br') as f:
                            s = f.read().decode('utf-8')
                            delim = '\r\n\r\n'
                            if s.find(delim) == -1:
                                delim = '\n\n'
                            for sql in s.split(delim):
                                sql = sql.strip()
                                #print(sql)
                                if sql:
                                    cursor.execute(sql)
        return True

    def import_styles(self):
        # Request styles modified after start_date from Teamwork API
        # and save results to MySQL DB.
        # Each next run will use start_date according to previous run

        with self.db.cursor() as cursor:
            # We are starting from the modification time of the last received record
            cursor.execute('select max(RecModified) as startdate from StyleStream;')
            row = cursor.fetchone()
            if row['startdate']:
                self.start_date = row['startdate']
                if self.shift_ms:
                    self.start_date += datetime.timedelta(milliseconds=self.shift_ms)

        start_date_ = self.start_date
        print(f'\tRequesting {self.url} for Styles modified from\t{start_date_}...')
        start_date_ = start_date_.isoformat(timespec='milliseconds')
        self.multi_chunk_import('<Filters>'
                                f'<Filter Field="RecModified" Operator="Greater than or equal" Value="{start_date_}" />'
                                '</Filters>'
                                '<SortDescriptions>'
                                '<SortDescription Name="RecModified" Direction="Ascending" />'
                                '</SortDescriptions>',
                                'inventory-export',
                                self._process_styles_xml)

    def _process_rta_xml(self, xml_root):
        # Copy Styles to Items
        done = 0
        for rta in xml_root.iter('LocationQuantity'):
            try:
                done += 1
                itemid = rta.find('ItemIdentifier').text
                qty = (float(rta.find('Qty').text) -
                       float(rta.find('CommittedQty').text) -
                       float(rta.find('DamagedQty').text))
                with self.db.cursor() as cursor:
                    cursor.execute('INSERT INTO Items (ItemId, Qty, LocCount, QtySent, QtyApiRequestTime) '
                                   'VALUES (%s, %s, 1, NULL, %s) '
                                   'ON DUPLICATE KEY UPDATE '
                                   'QtySent = NULL, '
                                   'Qty = case when QtyApiRequestTime = %s then Qty else 0 end + %s, '
                                   'LocCount = case when QtyApiRequestTime = %s then LocCount else 0 end + 1, '
                                   'QtyApiRequestTime = %s',
                                   (itemid, qty, self.apiRequestTime,
                                    self.apiRequestTime, qty,
                                    self.apiRequestTime,
                                    self.apiRequestTime,
                                    ))
            except Exception as e:
                print('\t\t\t', e)
        if done > 0:
            print(f'\t\t\tRTA: {done} received, saved to DB "{twmysql.HOST} {twmysql.DB}"')
            self.save_last_response('-rta')
        return done

    def import_rta_by_item(self, item_id):
        # Request RTA by ItemId from Teamwork API
        # and save results to MySQL DB
        print(f'\tRequesting {self.url} for RTA on Item {item_id}...')

        self.db.autocommit(False)
        try:
            self.multi_chunk_import('<Settings>'
                                    '<ItemIdentifierSetting>TeamworkId</ItemIdentifierSetting>'
                                    '<LocationIdentifierSetting>TeamworkId</LocationIdentifierSetting>'
                                    '</Settings>'
                                    '<Filters>'
                                    f'<Filter Field="ItemId" Operator="Equal" Value="{item_id}" />'
                                    f'<Filter Field="LocationId" Operator="Contains" Value="{_locs}" />'
                                    '</Filters>',
                                    'location-quantity-export',
                                    self._process_rta_xml
                                    )
            self.db.commit()
        except:
            self.db.rollback()
            raise
        finally:
            self.db.autocommit(True)

    def import_rta_by_date(self, date=None, run_by_item_at_the_end=False):
        # Request RTA modified after date from Teamwork API
        # and save results to MySQL DB
        if not date:
            with self.db.cursor() as cursor:
                cursor.execute('SELECT MAX(QtyApiRequestTime) startdate FROM Items ')
                row = cursor.fetchone()
                if row['startdate']:
                    date = row['startdate']
                    if self.shift_ms:
                        date += datetime.timedelta(milliseconds=self.shift_ms)
                else:
                    date = START_DATE

        print(f'\tRequesting {self.url} for RTA data modified from\t{date}...')
        self.db.autocommit(False)
        try:
            self.multi_chunk_import('<Settings>'
                                    '<ItemIdentifierSetting>TeamworkId</ItemIdentifierSetting>'
                                    '<LocationIdentifierSetting>TeamworkId</LocationIdentifierSetting>'
                                    '</Settings>'
                                    '<Filters>'
                                    # f'<Filter Field="ItemId" Operator="Equal" Value="9E925D6D-6398-4B29-828C-1A5BE8600F00" />'
                                    f'<Filter Field="RecModified" Operator="Greater than or equal" Value="{date}" />'
                                    f'<Filter Field="LocationId" Operator="Contains" Value="{_locs}" />'
                                    '</Filters>',
                                    'location-quantity-export',
                                    self._process_rta_xml)
            self.db.commit()
        except:
            self.db.rollback()
            raise
        finally:
            self.db.autocommit(True)

        if run_by_item_at_the_end:
            with self.db.cursor() as cursor:
                cursor.execute('select ItemId from Items where LocCount < %s and Qty is not Null',
                               (_loc_count,))
                while True:
                    row = cursor.fetchone()
                    if not row:
                        break
                    self.import_rta_by_item(row['ItemId'])


if __name__ == '__main__':

    tw = Teamwork2Shopify()

    # Command line arguments processing
    parser = argparse.ArgumentParser(description=f'Getting Teamwork Inventory from {tw.url}')
    parser.add_argument('--chunk', type=int, help=f'Chunk Size ({tw.chunk_size})')
    parser.add_argument('--start', help=f'Start Date ({tw.start_date})')
    parser.add_argument('--drop', nargs='?', type=bool, const=False,
                        help=f'Drop tables in Target DB')
    args = parser.parse_args()
    if args.chunk is not None:
        tw.chunk_size = int(args.chunk)
    if args.start is not None:
        tw.start_date = args.start

    if tw.init_tw(args.drop):
        #import_rta_by_item('9E925D6D-6398-4B29-828C-1A5BE8600F00')
        tw.import_styles()
        tw.import_rta_by_date()  #dateutil.parser.parse('2000-01-01 00:00:00'))
