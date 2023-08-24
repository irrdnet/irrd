import gzip
import logging
import os
import shutil
from io import BytesIO
from tempfile import NamedTemporaryFile
from typing import IO, Any, Tuple
from urllib import request
from urllib.error import URLError
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)
DOWNLOAD_TIMEOUT = 10


def retrieve_file(url: str, return_contents=True) -> Tuple[str, bool]:
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
    url_parsed = urlparse(url)

    if url_parsed.scheme in ["ftp", "http", "https"]:
        return _retrieve_file_download(url, url_parsed, return_contents)
    if url_parsed.scheme == "file":
        return _retrieve_file_local(url_parsed.path, return_contents)

    raise ValueError(f"Invalid URL: {url} - scheme {url_parsed.scheme} is not supported")


def _retrieve_file_download(url, url_parsed, return_contents=False) -> Tuple[str, bool]:
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
        logger.info(f"Downloaded {url}, contained {value}")
        return value, False
    else:
        if url.endswith(".gz"):
            zipped_file = destination
            zipped_file.close()
            destination = NamedTemporaryFile(delete=False)
            logger.debug(f"Downloaded file is expected to be gzipped, gunzipping from {zipped_file.name}")
            with gzip.open(zipped_file.name, "rb") as f_in:
                shutil.copyfileobj(f_in, destination)  # type: ignore
            os.unlink(zipped_file.name)

        destination.close()

        logger.info(f"Downloaded (and gunzipped if applicable) {url} to {destination.name}")
        return destination.name, True


def _download_file(destination: IO[Any], url: str, url_parsed):
    """
    Download a file from HTTP(s) or FTP.
    The file contents are written to the destination parameter,
    which can be a BytesIO() or a regular file.
    """
    if url_parsed.scheme == "ftp":
        try:
            r = request.urlopen(url, timeout=DOWNLOAD_TIMEOUT)
            shutil.copyfileobj(r, destination)
        except URLError as error:
            raise OSError(f"Failed to download {url}: {str(error)}")
    elif url_parsed.scheme in ["http", "https"]:
        r = requests.get(url, stream=True, timeout=DOWNLOAD_TIMEOUT)
        if r.status_code == 200:
            for chunk in r.iter_content(10240):
                destination.write(chunk)
        else:
            raise OSError(f"Failed to download {url}: {r.status_code}: {str(r.content)}")


def _retrieve_file_local(path, return_contents=False) -> Tuple[str, bool]:
    if not return_contents:
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
