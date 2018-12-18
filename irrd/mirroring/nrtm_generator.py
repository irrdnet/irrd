from typing import Optional


class NRTMGeneratorException(Exception):
    pass


class NRTMGenerator:

    def generate(self, source: str, version: str, serial_start: int, serial_end: Optional[int]):
        raise NotImplementedError()
