import time
import json
from typing import Dict, Optional
from typing import Sequence


def get_chunk_tags(chunks: Dict, attrs: str):
    """
    Get tags for
    :param chunks:
    :param attrs:
    :return:
    """
    tags = []
    for chunk in chunks:
        resource_type = chunk['resource_type']
        url = chunk['url']
        if resource_type == 'js':
            tags.append(f'<script type="text/javascript" src="{url}" {attrs}></script>')
        if resource_type == 'css':
            tags.append(f'<link type="text/css" href="{url}" rel="stylesheet" {attrs}/>')
    return tags


class WebpackEntryPointLoader():

    extensions_by_resource_type = {
        'js': ('js', 'js.gz'),
        'css': ('css', 'css.gz'),
    }

    config: Dict

    def __init__(self, config: Dict):
        self.config = config

    def load_stats(self) -> Dict:
        """
        Example of valid json file strucures:
        When compiling:

        {
          "status": "compiling",
        }

        Error:
        {
          "status": "error",
          "resource": "/path/to/file.js",
          "error": "ModuleBuildError",
          "message": "Module build failed <snip>"
        }

        Compiled:
        {
          "status": "done",
          "entrypoints": {
            "admin": [
              {
                "name": "runtime.bundle.js",
                "contentHash": "e2b781da02d36dad3aff"
              },
              {
                "name": "vendor.bundle.js",
                "contentHash": "774c52f57ce30a5e1382"
              },
              {
                "name": "common.bundle.js",
                "contentHash": "639269b921c8cf869c5f"
              },
              {
                "name": "common.bundle.css",
                "contentHash": "d60a0fa36613ea58a23d"
              }
              {
                "name": "admin.bundle.js",
                "contentHash": "c78fb252d4e00207afef"
              },
            ],
            "app": [
              {
                "name": "runtime.bundle.js",
                "contentHash": "e2b781da02d36dad3aff"
              },
              {
                "name": "vendor.bundle.js",
                "contentHash": "774c52f57ce30a5e1382"
              },
              {
                "name": "common.bundle.js",
                "contentHash": "639269b921c8cf869c5f"
              },
              {
                "name": "common.bundle.css",
                "contentHash": "d60a0fa36613ea58a23d"
              },
              {
                "name": "app.bundle.js",
                "contentHash": "806fc65dbad8a4dbb1cc"
              },
            ]
          },
          "publicPath": "http://hostname/"
        }
        :return: Dict
        """
        with open(self.config['STATS_FILE'], encoding="utf-8") as f:
            stats = json.load(f)
            if stats['status'] not in ['error', 'compiling', 'done']:
                raise ValueError('Badly formatted stats file received')
            return stats

    def get_resource_type(self, chunk: Dict) -> Optional[str]:
        for resource_type, extensions in self.extensions_by_resource_type.items():
            if chunk['name'].endswith(extensions):
                return resource_type
        return None

    def get_chunk_url(self, public_path: str, chunk: Dict) -> str:
        name = chunk['name']
        hash = chunk['contentHash']
        query = '' if not hash else f'?{hash}'
        return f'{public_path}{name}{query}'

    def filter_chunks(self, public_path: str, chunks: Sequence[Dict], required_resource_type:str) -> Sequence[Dict]:
        if required_resource_type not in self.extensions_by_resource_type:
            valid_resource_types = ', '.join(self.extensions_by_resource_type.keys())
            raise ValueError(f'Invalid chunk type {required_resource_type}. Must be one of: {valid_resource_types}')
        for chunk in chunks:
            resource_type = self.get_resource_type(chunk)
            if required_resource_type == resource_type:
                yield {
                    'url': self.get_chunk_url(public_path, chunk),
                    'resource_type': resource_type,
                    **chunk,
                }

    def get_chunks_for_entry_point(self, entry_point_name:str, resource_type:str) -> Sequence[Dict]:
        stats = self.load_stats()

        if stats['status'] == 'compiling':
            while stats['status'] == 'compiling':
                time.sleep(0.1)
                stats = self.load_stats()

        if stats['status'] == 'error':
            error = f"""
            {stats['error']} in {stats['resource']}

            {stats['message']}
            """
            raise ValueError(error)

        entry_point = stats['entrypoints'].get(entry_point_name)
        if not entry_point:
            known_entry_points = ', '.join(stats['entrypoints'].keys())
            raise ValueError(f'Invalid entry point {entry_point_name}. Known entry points: {known_entry_points}')
        public_path = stats['publicPath']

        return self.filter_chunks(public_path, entry_point, resource_type)
