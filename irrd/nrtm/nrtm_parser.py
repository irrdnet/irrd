import logging
import re
from typing import List

from .nrtm_operation import NRTMOperation
from irrd.storage.models import DatabaseOperation

logger = logging.getLogger(__name__)
start_line_re = re.compile(r'^% *START *Version: *(?P<version>\d+) +(?P<source>\w+) +(?P<first_serial>\d+)-(?P<last_serial>\d+)$')


class NRTMParser:
    """
    The NRTM parser takes the data of an NRTM string, and splits it
    into individual operations, matched with their serial and
    whether they are an ADD/DEL operation.

    Creating an instance will fill the attributes:
    - first_serial: the first serial found in the data
    - last_serial: the last serial found
    - source: the RPSL source recorded in the START header
    - objects: a list of NRTMOperation objects

    Raises a ValueError for invalid NRTM data.
    """
    first_serial = -1
    last_serial = -1
    source = None
    _current_op_serial = -1

    def __init__(self, nrtm_data: str) -> None:
        self.operations: List[NRTMOperation] = []
        self._split_stream(nrtm_data)

    def _split_stream(self, data: str) -> None:
        """Split a stream into individual operations."""
        lines = iter(data.splitlines())

        for line in lines:
            if self._handle_possible_start_line(line):
                continue
            elif line.startswith("%") or line.startswith("#"):
                continue
            elif line.startswith('ADD') or line.startswith('DEL'):
                self._handle_operation(line, lines)

        if self._current_op_serial != self.last_serial:
            msg = f'NRTM stream error: expected operations up to and including serial {self.last_serial}, ' \
                  f'last operation was {self._current_op_serial}'
            logger.error(msg)
            raise ValueError(msg)

    def _handle_possible_start_line(self, line: str) -> bool:
        """Check whether a line is an NRTM START line, and if so, handle it."""
        start_line_match = start_line_re.match(line)
        if not start_line_match:
            return False

        if self.source:  # source can only be defined if this is a second START line
            msg = f'Encountered second START line in NRTM stream, first was {self.source} ' \
                  f'{self.first_serial}-{self.last_serial}, new line is: {line}'
            logger.error(msg)
            raise ValueError(msg)

        self.version = start_line_match.group('version')
        self.source = start_line_match.group('source')
        self.first_serial = int(start_line_match.group('first_serial'))
        self.last_serial = int(start_line_match.group('last_serial'))

        if self.version not in ['1', '3']:
            msg = f'Invalid NRTM version {self.version} in NRTM start line: {line}'
            logger.error(msg)
            raise ValueError(msg)

        return True

    def _handle_operation(self, current_line: str, lines) -> None:
        """Handle a single ADD/DEL operation."""
        if self._current_op_serial == -1:
            self._current_op_serial = self.first_serial
        else:
            self._current_op_serial += 1

        if ' ' in current_line:
            operation_str, line_serial_str = current_line.split(' ')
            line_serial = int(line_serial_str)
            if line_serial != self._current_op_serial:
                msg = f'Invalid NRTM serial: ADD/DEL has serial {line_serial}, ' \
                      f'expected {self._current_op_serial}'
                logger.error(msg)
                raise ValueError(msg)
        else:
            operation_str = current_line.strip()
        operation = DatabaseOperation(operation_str)

        next(lines)  # Discard empty line
        current_obj = ""
        while True:
            try:
                object_line = next(lines)
            except StopIteration:
                break
            if not object_line.strip('\r\n'):
                break
            current_obj += object_line + "\n"

        nrtm_operation = NRTMOperation(operation, self._current_op_serial, current_obj)
        self.operations.append(nrtm_operation)
