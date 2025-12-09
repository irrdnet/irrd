import gzip
import hashlib
import logging
import os
import pathlib
import shutil
from io import BytesIO
from tempfile import NamedTemporaryFile
from typing import IO, Any
from urllib import request
from urllib.error import URLError
from urllib.parse import urlparse

import requests
from cryptography.hazmat.primitives import constant_time
from pydantic_core import Url

from irrd.conf import get_setting
from irrd.conf.defaults import HTTP_USER_AGENT

logger = logging.getLogger(__name__)


def retrieve_file(url: Url | str, return_contents=True, expected_hash: str | None = None) -> tuple[str, bool]:
    """
    Retrieve a file from either HTTP(s), FTP or local disk.

    If return_contents is True, the file is read, stripped and then the
    contents are returned. If return_contents is False, the path to a
    local file is returned where the data can be read.

    Return value is a tuple of the contents of the file, or the path to
    the local file, and a boolean to indicate whether the caller should
    unlink the path later.

    If the URL ends in .gz, the file is gunzipped before being processed,
    but only for HTTP(s) and FTP downloads.
    """
    url_parsed = urlparse(str(url))

    if url_parsed.scheme in ["ftp", "http", "https"]:
        return _retrieve_file_download(str(url), url_parsed, return_contents, expected_hash)
    if url_parsed.scheme == "file":
        return _retrieve_file_local(url_parsed.path, return_contents, expected_hash)

    raise ValueError(f"Invalid URL: {url} - scheme {url_parsed.scheme} is not supported")


def _retrieve_file_download(
    url: str, url_parsed, return_contents=False, expected_hash: str | None = None
) -> tuple[str, bool]:
    """
    Retrieve a file from HTTP(s) or FTP

    If return_contents is False, the file is read, stripped and then the
    contents are returned. If return_contents is True, the data is written
    to a temporary file, and the path of this file is returned.
    It is the responsibility of the caller to unlink this path later.

    If the URL ends in .gz, the file is gunzipped before being processed,
    but only if return_contents is False.
    """
    destination: IO[Any]
    if return_contents:
        destination = BytesIO()
    else:
        destination = NamedTemporaryFile(delete=False)
    _download_file(destination, url, url_parsed)
    if return_contents:
        value = destination.getvalue().decode("utf-8").strip()  # type: ignore
        logger.info(f"Downloaded {url}")
        return value, False
    else:
        destination.close()
        check_file_hash_sha256(destination.name, expected_hash)
        if url.endswith(".gz"):
            zipped_file = destination

            destination = NamedTemporaryFile(delete=False)
            with gzip.open(zipped_file.name, "rb") as f_in:
                shutil.copyfileobj(f_in, destination)  # type: ignore
            os.unlink(zipped_file.name)

        logger.info(f"Downloaded (and gunzipped if applicable) {url} to {destination.name}")
        return destination.name, True


def _download_file(destination: IO[Any], url: str, url_parsed):
    """
    Download a file from HTTP(s) or FTP.
    The file contents are written to the destination parameter,
    which can be a BytesIO() or a regular file.
    """
    download_timeout = int(get_setting("download_timeout"))
    if url_parsed.scheme == "ftp":
        try:
            r = request.urlopen(url, timeout=download_timeout)
            shutil.copyfileobj(r, destination)
        except URLError as error:
            raise OSError(f"Failed to download {url}: {str(error)}")
    elif url_parsed.scheme in ["http", "https"]:
        r = requests.get(url, stream=True, timeout=download_timeout, headers={"User-Agent": HTTP_USER_AGENT})
        if r.status_code == 200:
            for chunk in r.iter_content(10240):
                destination.write(chunk)
        else:
            raise OSError(f"Failed to download {url}: {r.status_code}: {str(r.content)}")


def _retrieve_file_local(path, return_contents=False, expected_hash: str | None = None) -> tuple[str, bool]:
    if not return_contents:
        check_file_hash_sha256(path, expected_hash)
        if path.endswith(".gz"):
            destination = NamedTemporaryFile(delete=False)
            logger.debug(f"Local file is expected to be gzipped, gunzipping from {path}")
            with gzip.open(path, "rb") as f_in:
                shutil.copyfileobj(f_in, destination)
            destination.close()
            return destination.name, True
        else:
            return path, False
    with open(path) as fh:
        value = fh.read().strip()
    return value, False


def check_file_hash_sha256(filename: str, expected_hash: str | None) -> None:
    """
    Check whether the contents of a file match an expected SHA256 hash.
    expected_hash should be a hex digest.
    """
    if not expected_hash:
        return
    file_hash = file_hash_sha256(filename)

    if not constant_time.bytes_eq(file_hash.digest(), bytes.fromhex(expected_hash)):
        raise ValueError(
            f"Invalid hash in {filename}: expected {expected_hash}, found {file_hash.hexdigest()}"
        )


def file_hash_sha256(filename: str | pathlib.Path):
    """Calculate the SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(filename, "rb") as f:
        # Read and update hash in chunks of 4K
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash
