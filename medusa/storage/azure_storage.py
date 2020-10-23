import base64
import io
import json
import logging
import os

from dateutil import parser
from libcloud.storage.drivers.azure_blobs import AzureBlobsStorageDriver

from medusa.storage.abstract_storage import AbstractStorage
import medusa


class AzureStorage(AbstractStorage):

    def connect_storage(self):
        with io.open(os.path.expanduser(self.config.key_file), 'r', encoding='utf-8') as json_fi:
            credentials = json.load(json_fi)

        driver = AzureBlobsStorageDriver(
            key=credentials['storage_account'],
            secret=credentials['key']
        )

        return driver

    def get_object_datetime(self, blob):
        logging.debug(
            "Blob {} last modification time is {}".format(
                blob.name, blob.extra["last_modified"]
            )
        )
        return parser.parse(blob.extra["last_modified"])

    def get_cache_path(self, path):
        logging.debug(
            "My cache path is {}".format(path)
        )
        return path

    def upload_blobs(self, src, dest):
        manifest = medusa.storage.concurrent.upload_blobs(
            self, src, dest, self.bucket,
            max_workers=self.config.concurrent_transfers
        )
        objects = self.list_objects(dest)
        new_manifest = []
        for obj in objects:
            for item in manifest:
                if (item.MD5 == obj.hash):
                    new_manifest.append(medusa.storage.ManifestObject(obj.name, obj.size, obj.extra['md5_hash']))
                    break
        return new_manifest

    @staticmethod
    def blob_matches_manifest(blob, object_in_manifest):
        return AzureStorage.compare_with_manifest(
            actual_size=blob.size,
            size_in_manifest=object_in_manifest['size'],
            actual_hash=blob.extra['md5_hash'],
            hash_in_manifest=object_in_manifest['MD5']
        )

    @staticmethod
    def file_matches_cache(src, cached_item, threshold=None):
        return AzureStorage.compare_with_manifest(
            actual_size=src.stat().st_size,
            size_in_manifest=cached_item['size'],
            actual_hash=AbstractStorage.generate_md5_hash(src),
            hash_in_manifest=cached_item['MD5']
        )

    @staticmethod
    def compare_with_manifest(actual_size, size_in_manifest, actual_hash=None, hash_in_manifest=None, threshold=None):
        sizes_match = actual_size == size_in_manifest

        hashes_match = (
            # this case comes from comparing blob hashes to manifest entries (in context of Azure)
            actual_hash == base64.b64decode(hash_in_manifest).hex()
            # this comes from comparing files to a cache
            or hash_in_manifest == base64.b64decode(actual_hash).hex()
            # and perhaps we need the to check for match even without base64 encoding
            or actual_hash == hash_in_manifest
        )

        return sizes_match and hashes_match
