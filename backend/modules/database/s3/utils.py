"""
S3 utility functions
"""

import gzip
from typing import Union


def compress_data(data: Union[str, bytes]) -> bytes:
    """Compress data using gzip"""
    if isinstance(data, str):
        data = data.encode('utf-8')
    return gzip.compress(data)


def decompress_data(compressed_data: bytes) -> str:
    """Decompress gzipped data"""
    return gzip.decompress(compressed_data).decode('utf-8')