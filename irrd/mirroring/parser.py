import logging
import re
from typing import List, Set

from irrd.conf import get_setting
from irrd.rpsl.parser import UnknownRPSLObjectClassException
from irrd.rpsl.rpsl_objects import rpsl_object_from_text
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.models import DatabaseOperation
from irrd.utils.text import split_paragraphs_rpsl
from .nrtm_operation import NRTMOperation

logger = logging.getLogger(__name__)
nrtm_start_line_re = re.compile(r'^% *START *Version: *(?P<version>\d+) +(?P<source>[\w-]+) +(?P<first_serial>\d+)-(?P<last_serial>\d+)( FILTERED)?\n$', flags=re.MULTILINE)


class MirrorParser:
    def __init__(self):
        object_class_filter = get_setting(f'sources.{self.source}.object_class_filter')
        if object_class_filter:
            if isinstance(object_class_filter, str):
                object_class_filter = [object_class_filter]
            self.object_class_filter = [c.strip().lower() for c in object_class_filter]
        else:
            self.object_class_filter = None


class MirrorFileImportParser(MirrorParser):
    """
    This parser handles imports of files for mirror databases.
    Note that this parser can be called multiple times for a single
    full import, as some databases use split files.
    """
    obj_parsed = 0  # Total objects found
    obj_errors = 0  # Objects with errors
    obj_ignored_class = 0  # Objects ignored due to object_class_filter setting
    obj_unknown = 0  # Objects with unknown classes
    unknown_object_classes: Set[str] = set()  # Set of encountered unknown classes

    def __init__(self, source: str, filename: str, serial: int, database_handler: DatabaseHandler) -> None:
        logger.debug(f'Starting file import of {source} from {filename}, setting serial {serial}')
        self.source = source
        self.filename = filename
        self.serial = serial
        self.database_handler = database_handler
        super().__init__()

        self.run_import()

    def run_import(self):
        f = open(self.filename, encoding="utf-8", errors='backslashreplace')
        for paragraph in split_paragraphs_rpsl(f):
            self.parse_object(paragraph)

        self.log_report()

    def parse_object(self, rpsl_text: str) -> None:
        try:
            self.obj_parsed += 1
            obj = rpsl_object_from_text(rpsl_text.strip(), strict_validation=False)

            if obj.messages.errors():
                logger.critical(f'Parsing errors occurred while importing from file for {self.source}. '
                                f'This object is ignored, causing potential data inconsistencies. A new operation for '
                                f'this update, without errors, will still be processed and cause the inconsistency to '
                                f'be resolved. Parser error messages: {obj.messages.errors()}; '
                                f'original object text follows:\n{rpsl_text}')
                self.database_handler.record_mirror_error(self.source, f'Parsing errors: {obj.messages.errors()}, '
                                                                       f'original object text follows:\n{rpsl_text}')
                self.obj_errors += 1
                return

            if obj.source() != self.source:
                msg = f'Invalid source {obj.source()} for object {obj.pk()}, expected {self.source}'
                logger.critical(msg)
                self.database_handler.record_mirror_error(self.source, msg)
                self.obj_errors += 1
                return

            if self.object_class_filter and obj.rpsl_object_class.lower() not in self.object_class_filter:
                self.obj_ignored_class += 1
                return

            self.database_handler.upsert_rpsl_object(obj, forced_serial=self.serial)

        except UnknownRPSLObjectClassException as e:
            self.obj_unknown += 1
            self.unknown_object_classes.add(str(e).split(":")[1].strip())

    def log_report(self) -> None:
        obj_successful = self.obj_parsed - self.obj_unknown - self.obj_errors - self.obj_ignored_class
        logger.info(f"File import for {self.source}: {self.obj_parsed} objects read, "
                    f"{obj_successful} objects inserted, "
                    f"ignored {self.obj_errors} due to errors, "
                    f"ignored {self.obj_ignored_class} due to object_class_filter, "
                    f"serial {self.serial}, source {self.filename}")
        if self.obj_unknown:
            unknown_formatted = ', '.join(self.unknown_object_classes)
            logger.warning(f"Ignored {self.obj_unknown} objects found in file import for {self.source} due to unknown "
                           f"object classes: {unknown_formatted}")


class NRTMStreamParser(MirrorParser):
    """
    The NRTM parser takes the data of an NRTM string, and splits it
    into individual operations, matched with their serial and
    whether they are an ADD/DEL operation.

    Creating an instance will fill the attributes:
    - first_serial: the first serial found in the data
    - last_serial: the last serial found
    - nrtm_source: the RPSL source recorded in the START header (must be equal to expected source)
    - operations: a list of NRTMOperation objects

    Raises a ValueError for invalid NRTM data.
    """
    first_serial = -1
    last_serial = -1
    nrtm_source = None
    _current_op_serial = -1

    def __init__(self, source: str, nrtm_data: str, database_handler: DatabaseHandler) -> None:
        self.source = source
        self.database_handler = database_handler
        super().__init__()
        self.operations: List[NRTMOperation] = []
        self._split_stream(nrtm_data)

    def _split_stream(self, data: str) -> None:
        """Split a stream into individual operations."""
        paragraphs = split_paragraphs_rpsl(data, strip_comments=False)

        for paragraph in paragraphs:
            if self._handle_possible_start_line(paragraph):
                continue
            elif paragraph.startswith("%") or paragraph.startswith("#"):
                continue  # pragma: no cover -- falsely detected as not run by coverage library
            elif paragraph.startswith('ADD') or paragraph.startswith('DEL'):
                self._handle_operation(paragraph, paragraphs)

        if self._current_op_serial > self.last_serial and self.version != '3':
            msg = f'NRTM stream error for {self.source}: expected operations up to and including serial ' \
                  f'{self.last_serial}, last operation was {self._current_op_serial}'
            logger.error(msg)
            self.database_handler.record_mirror_error(self.source, msg)
            raise ValueError(msg)

        if self.last_serial > 0:
            self.database_handler.force_record_serial_seen(self.source, self.last_serial)

    def _handle_possible_start_line(self, line: str) -> bool:
        """Check whether a line is an NRTM START line, and if so, handle it."""
        start_line_match = nrtm_start_line_re.match(line)
        if not start_line_match:
            return False

        if self.nrtm_source:  # nrtm_source can only be defined if this is a second START line
            msg = f'Encountered second START line in NRTM stream, first was {self.source} ' \
                  f'{self.first_serial}-{self.last_serial}, new line is: {line}'
            self.database_handler.record_mirror_error(self.source, msg)
            logger.error(msg)
            raise ValueError(msg)

        self.version = start_line_match.group('version')
        self.nrtm_source = start_line_match.group('source').upper()
        self.first_serial = int(start_line_match.group('first_serial'))
        self.last_serial = int(start_line_match.group('last_serial'))

        if self.source != self.nrtm_source:
            msg = f'Invalid NRTM source in START line: expected {self.source} but found ' \
                  f'{self.nrtm_source} in line: {line}'
            self.database_handler.record_mirror_error(self.source, msg)
            logger.error(msg)
            raise ValueError(msg)

        if self.version not in ['1', '3']:
            msg = f'Invalid NRTM version {self.version} in START line: {line}'
            self.database_handler.record_mirror_error(self.source, msg)
            logger.error(msg)
            raise ValueError(msg)

        logger.debug(f'Found valid start line for {self.source}, range {self.first_serial}-{self.last_serial}')

        return True

    def _handle_operation(self, current_paragraph: str, paragraphs) -> None:
        """Handle a single ADD/DEL operation."""
        if not self.nrtm_source:
            msg = f'Encountered operation before valid NRTM START line, paragraph encountered: {current_paragraph}'
            self.database_handler.record_mirror_error(self.source, msg)
            logger.error(msg)
            raise ValueError(msg)

        if self._current_op_serial == -1:
            self._current_op_serial = self.first_serial
        else:
            self._current_op_serial += 1

        if ' ' in current_paragraph:
            operation_str, line_serial_str = current_paragraph.split(' ')
            line_serial = int(line_serial_str)
            # Gaps are allowed, but the line serial can never be lower, as that
            # means operations are served in the wrong order.
            if line_serial < self._current_op_serial:
                msg = f'Invalid NRTM serial for {self.source}: ADD/DEL has serial {line_serial}, ' \
                      f'expected at least {self._current_op_serial}'
                logger.error(msg)
                self.database_handler.record_mirror_error(self.source, msg)
                raise ValueError(msg)
            self._current_op_serial = line_serial
        else:
            operation_str = current_paragraph.strip()

        operation = DatabaseOperation(operation_str)
        object_text = next(paragraphs)
        nrtm_operation = NRTMOperation(self.source, operation, self._current_op_serial,
                                       object_text, self.object_class_filter)
        self.operations.append(nrtm_operation)
