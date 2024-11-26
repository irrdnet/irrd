from collections.abc import Generator, Iterable
from gzip import GzipFile
from typing import IO, Any, Union

import ujson

RS = b"\x1e"
CHUNK_SIZE = 1024 * 100


def jsonseq_decode(input_stream: IO[bytes]) -> Generator[dict, None, None]:
    """
    Decode a byte stream with RFC7464 JSON sequences.
    Returns a generator with all contained objects, decoded.
    """
    buffer = b""

    def yield_buffer():
        nonlocal buffer
        while RS in buffer:
            *sequences, buffer = buffer.split(RS)
            for sequence in sequences:
                if sequence:
                    yield ujson.loads(sequence)

    while True:
        chunk = input_stream.read(CHUNK_SIZE)
        if not chunk:
            yield from yield_buffer()
            if buffer:
                yield ujson.loads(buffer)
            break
        buffer += chunk
        yield from yield_buffer()


def jsonseq_encode(input_stream: Iterable[Any], output_stream: Union[IO[bytes], GzipFile]):
    """
    Encode a byte stream with RFC7464 JSON sequences.
    Reads objects from the input iterable, writes the bytes to the output stream.
    """
    for input_item in input_stream:
        jsonseq_encode_one(input_item, output_stream)


def jsonseq_encode_one(input_item: Any, output_stream: Union[IO[bytes], GzipFile]):
    """
    Encode a byte stream with RFC7464 JSON sequences.
    Reads a single object and writes the bytes to the output stream.
    """
    input_encoded = ujson.dumps(input_item)
    output_stream.write(RS + input_encoded.encode("utf-8") + b"\n")
