# -*-coding:utf-8-*-
from django.core.files.storage import Storage
from fdfs_client.client import Fdfs_client


class FDFSStorage(Storage):
    '''fast dfs文件存储类'''
    def _open(self, name, model='rb'):
        '''打开文件时使用'''
        pass

    def _save(self, name, content):
        '''保存文件时使用'''
        # name: 你选择上传文件的名称
        # content: 包含你上传文件内容的file对象

        # 创建一个Fdfs_client对象
        client = Fdfs_client('./utils/client.conf')
        # 上传文件到fast dfs系统
        res = client.upload_appender_by_buffer(content.read())

        # return dict
        # {
        #     'Group name': group_name,
        #     'Remote file_id': remote_file_id,
        #     'Status': 'Upload successed.',
        #     'Local file name': '',
        #     'Uploaded size': upload_size,
        #     'Storage IP': storage_ip
        # } if success else None
        if res.get('Status') != 'Upload successed.':
            raise Exception('上传文件到fastDFS失败！请检查配置')

        # 获取返回的文件的ID
        filename = res.get('Remote file_id')

        return filename

    def exists(self, name):
        """Django判断文件名是否可用"""
        return False

    def url(self, name):
        """返回访问文件url路径"""
        return 'http://45.122.138.81:8888/' + name
