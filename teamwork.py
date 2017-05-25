import os
import re
import time
import requests # sudo python3.6 -m pip install requests
import xml.etree.ElementTree as ET

import utils

class Teamwork:
    _api_request_prefix = ('<ApiDocument xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
                           'xmlns="http://microsoft.com/wsdl/types/"><Request>')
    _api_request_suffix = '</Request></ApiDocument>'

    def __init__(self, api_key, url, chunk_size=100, max_wait=60, save_responses=True):
        self.api_key = api_key
        self.url = url
        self.chunk_size = chunk_size  # Number of records per one request
        self.max_wait = max_wait  # Max waiting time for Successfull status (seconds)
        self.save_responses = save_responses

        self.apiDocumentId = None
        self.apiRequestTime = None
        self.last_response = None
        self.skip = 0
        self.chunk_num = 0  # Current chunk number

    def save_last_response(self, suffix=''):
        # Saving XML Response content to file
        if self.save_responses and self.last_response:
            try:
                fn = os.path.join(utils._DIR, 'xml', utils.time_str() + suffix + str(self.chunk_num) + '.xml')
                print('\t\t\tSaving Response to', fn, '...')
                with open(fn, 'bw') as f:
                    f.write(self.last_response.content)
            except:
                pass

    @staticmethod
    def _get_root_from_response(response):
        # Get Root from XML Response, removing All XML NameSpaces
        s = re.sub(r'\sxmlns="[^\"]+"', '', response.content.decode('utf-8'), flags=re.MULTILINE)
        return ET.fromstring(s)

    def _get_xml_root(self, req, apitype):
        # Get XML on the request with thn api-type
        xml_root = None
        self.last_response = None
        data = {'Data': req,
                'Source': 'VC_Test', 'UseApiVersion2': 'true',
                'ApiKey': self.api_key, 'Async': 'true',
                'ApiRequestType': apitype}
        self.last_response = requests.post(self.url + 'api.ashx', data=data)
        xml_root = Teamwork._get_root_from_response(self.last_response)
        a = xml_root.attrib['ApiDocumentId']
        status = xml_root.attrib['Status']
        count = 0
        wait = 3
        while status == 'InProcess':
            time.sleep(wait)
            self.last_response = requests.post(self.url + 'ApiStatus.ashx', data={'ID': a})
            xml_root = self._get_root_from_response(self.last_response)
            status = xml_root.attrib['Status']
            count += 1
            if count > self.max_wait // wait:
                break
        if self.apiDocumentId is None and status == 'Successful':
            self.apiDocumentId = a  # None otherwise
        if 'apiRequestTime' in xml_root.attrib:
            self.apiRequestTime = xml_root.attrib['apiRequestTime']
        if status == 'Error':
            print('\t\t' + xml_root.attrib[status])
        return xml_root

    def multi_chunk_import(self, api_req, api_type, process_xml_function, one_chunk=False):
        # Processing of respond on API Request (without prefix/suffix) with API type
        # using method for XML processing
        self.apiDocumentId = None
        self.apiRequestTime = None
        self.chunk_num = 1
        self.skip = 0
        done = 0
        total_rec = '?'

        # Main Loop
        req = (Teamwork._api_request_prefix +
               api_req +
               f'<Top>{self.chunk_size}</Top>' +
               Teamwork._api_request_suffix)
        # print('\t\tSend API request:',req)
        xml_root = self._get_xml_root(req, api_type)
        if self.apiDocumentId is None:
            print("\tCan't get 'Successful' Status from Server!")
        else:
            if 'TotalRecords' in xml_root.attrib:
                total_rec = int(xml_root.attrib['TotalRecords'])
                if not one_chunk and (total_rec is None or total_rec > 0):
                    print(f'\t\tChunk #{self.chunk_num} {self.skip}/{total_rec}...')
            if process_xml_function:
                done = process_xml_function(xml_root)
            if not one_chunk:
                self.skip = done
                while done and done > 0 and (total_rec == '?' or self.skip < total_rec):
                    self.chunk_num += 1
                    print(f'\t\tChunk #{self.chunk_num} {self.skip}/{total_rec}...')
                    req = (Teamwork._api_request_prefix +
                           f'<ParentApiDocumentId>{self.apiDocumentId}</ParentApiDocumentId>'
                           f'<Top>{self.chunk_size}</Top>'
                           f'<Skip>{self.skip}</Skip>' +
                           Teamwork._api_request_suffix)
                    # print('\t\tSend API request:',req)
                    xml_root = self._get_xml_root(req, api_type)
                    done = process_xml_function(xml_root)
                    self.skip += done
