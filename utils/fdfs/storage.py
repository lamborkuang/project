from django.core.files.storage import Storage 
from django.conf import settings 
from fdfs_client.client import Fdfs_client 


class FDFSStorage(Storage):

    def __init__(self, client_conf=None, base_url = None):
        if client_conf is None:
            client_conf = settings.FDFS_CLIENT_CONF 
        self.client_conf = client_conf
    
        if base_url is None:
            base_url = settings.FDFS_URL 
        self.base_url = base_url 

    def _open(self, name, mode='rb'):
        pass 
    
    def _save(self, name, content):
        client = Fdfs_client(self.client_conf)
        res = client.upload_by_buffer(content.read())
        # {'Group name': 'group1', 
        # 'Remote file_id': 'group1/M00/00/00/wKjH8V6F7FeAb7ZhAAAmv27pX4k6628865', 
        # 'Status': 'Upload successed.', 'Local file name': '',
        #  'Uploaded size': '9.00KB', 'Storage IP': '192.168.199.241'}
        if res.get('Status') != 'Upload successed.':
            raise Exception('上传文件到fast dfs失败')
        
        filename = res.get('Remote file_id')
        return filename 
    
    def exists(self, name):
        return False 
    
    def url(self, name):
        return self.base_url + name 
        