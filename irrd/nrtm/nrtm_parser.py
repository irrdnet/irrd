import logging
import re
from typing import List, Set

from irrd.conf import get_setting
from irrd.rpsl.parser import UnknownRPSLObjectClassException
from irrd.rpsl.rpsl_objects import rpsl_object_from_text
from irrd.storage.models import DatabaseOperation
from .nrtm_operation import NRTMOperation

logger = logging.getLogger(__name__)
start_line_re = re.compile(r'^% *START *Version: *(?P<version>\d+) +(?P<source>\w+) +(?P<first_serial>\d+)-(?P<last_serial>\d+)')


class NRTMBulkParser:
    obj_parsed = 0
    obj_errors = 0
    obj_ignored_class = 0
    obj_unknown = 0
    unknown_object_classes: Set[str] = set()
    database_handler = None

    def __init__(self, source, filename, serial, strict_validation, database_handler):
        logger.debug(f'Running bulk import of {source} from {filename}, setting serial {serial}')
        self.serial = serial
        self.source = source
        self.database_handler = database_handler

        self.object_class_filter = get_setting(f'databases.{self.source}.object_class_filter')
        if self.object_class_filter:
            self.object_class_filter = [c.trim().lower() for c in self.object_class_filter.split(',')]

        f = open(filename, encoding="utf-8", errors='backslashreplace')

        current_obj = ""
        for line in f.readlines():
            if line.startswith("%") or line.startswith("#"):
                continue
            current_obj += line

            if not line.strip("\r\n"):
                self.parse_object(current_obj, strict_validation)
                current_obj = ""

        self.parse_object(current_obj, strict_validation)

        obj_successful = self.obj_parsed - self.obj_unknown - self.obj_errors - self.obj_ignored_class
        logger.info(f"Bulk imported for {self.source}: {self.obj_parsed} objects read, "
                    f"{obj_successful} objects inserted, "
                    f"ignored {self.obj_errors} due to errors,"
                    f"ignored {self.obj_ignored_class} objects due to the object class filter, "
                    f"serial {self.serial}")
        if self.obj_unknown:
            unknown_formatted = ', '.join(self.unknown_object_classes)
            logger.error(f"Ignored {self.obj_unknown} objects found in bulk import for {self.source} due to unknown "
                         f"object classes: {unknown_formatted}")

    def parse_object(self, rpsl_text, strict_validation):
        if not rpsl_text.strip():
            return
        try:
            self.obj_parsed += 1
            obj = rpsl_object_from_text(rpsl_text.strip(), strict_validation=strict_validation)

            if obj.messages.errors():
                logger.critical(f'Parsing errors occurred while importing initial dump from {self.source}. '
                                f'This object is ignored, causing potential data inconsistencies. A new operation for '
                                f'this update, without errors, will still be processed and cause the inconsistency to '
                                f'be resolved. Parser error messages: {obj.messages.errors()}; '
                                f'original object text follows:\n{rpsl_text}')
                self.obj_errors += 1
                return

            if self.object_class_filter and obj.rpsl_object_class.lower() not in self.object_class_filter:
                self.obj_ignored_class += 1
                return

            self.database_handler.upsert_rpsl_object(obj, forced_serial=self.serial)

        except UnknownRPSLObjectClassException as e:
            self.obj_unknown += 1
            self.unknown_object_classes.add(str(e).split(":")[1].strip())


class NRTMStreamParser:
    """
    The NRTM parser takes the data of an NRTM string, and splits it
    into individual operations, matched with their serial and
    whether they are an ADD/DEL operation.

    Creating an instance will fill the attributes:
    - first_serial: the first serial found in the data
    - last_serial: the last serial found
    - source: the RPSL source recorded in the START header
    - operations: a list of NRTMOperation objects

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
        self.source = start_line_match.group('source').upper()
        self.first_serial = int(start_line_match.group('first_serial'))
        self.last_serial = int(start_line_match.group('last_serial'))

        if self.version not in ['1', '3']:
            msg = f'Invalid NRTM version {self.version} in NRTM start line: {line}'
            logger.error(msg)
            raise ValueError(msg)

        logger.debug(f'Found valid start line for {self.source}, range {self.first_serial}-{self.last_serial}')

        return True

    def _handle_operation(self, current_line: str, lines) -> None:
        """Handle a single ADD/DEL operation."""
        if not self.source:
            msg = f'Encountered operation before NRTM START line, line encountered: {current_line}'
            logger.error(msg)
            raise ValueError(msg)

        if self._current_op_serial == -1:
            self._current_op_serial = self.first_serial
        else:
            self._current_op_serial += 1

        if ' ' in current_line:
            operation_str, line_serial_str = current_line.split(' ')
            line_serial = int(line_serial_str)
            # Gaps are allowed, but the line serial can never be lower, as that
            # means operations are served in the wrong order.
            if line_serial < self._current_op_serial:
                msg = f'Invalid NRTM serial for {self.source}: ADD/DEL has serial {line_serial}, ' \
                      f'expected at least {self._current_op_serial}'
                logger.error(msg)
                raise ValueError(msg)
            self._current_op_serial = line_serial
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

        nrtm_operation = NRTMOperation(self.source, operation, self._current_op_serial, current_obj)
        self.operations.append(nrtm_operation)
