from typing import Optional

from irrd.conf import get_setting
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.queries import DatabaseStatusQuery, RPSLDatabaseJournalQuery
from irrd.utils.text import remove_auth_hashes as remove_auth_hashes_func


class NRTMGeneratorException(Exception):  # noqa: N818
    pass


class NRTMGenerator:
    def generate(
        self,
        source: str,
        version: str,
        serial_start_requested: int,
        serial_end_requested: Optional[int],
        database_handler: DatabaseHandler,
        remove_auth_hashes=True,
    ) -> str:
        """
        Generate an NRTM response for a particular source, serial range and
        NRTM version. Raises NRTMGeneratorException for various error conditions.

        For queries where the user requested NRTM updates up to LAST,
        serial_end_requested is None.
        """
        if not get_setting(f"sources.{source}.keep_journal"):
            raise NRTMGeneratorException("No journal kept for this source, unable to serve NRTM queries")

        q = DatabaseStatusQuery().source(source)
        try:
            status = next(database_handler.execute_query(q))
        except StopIteration:
            raise NRTMGeneratorException("There are no journal entries for this source.")

        if serial_end_requested and serial_end_requested < serial_start_requested:
            raise NRTMGeneratorException(
                f"Start of the serial range ({serial_start_requested}) must be lower or "
                f"equal to end of the serial range ({serial_end_requested})"
            )

        serial_start_available = status["serial_oldest_journal"]
        serial_end_available = status["serial_newest_journal"]

        if serial_start_available is None or serial_end_available is None:
            return "% Warning: there are no updates available"

        if serial_start_requested < serial_start_available:
            raise NRTMGeneratorException(
                f"Serials {serial_start_requested} - {serial_start_available} do not exist"
            )

        if serial_end_requested is not None and serial_end_requested > serial_end_available:
            raise NRTMGeneratorException(
                f"Serials {serial_end_available} - {serial_end_requested} do not exist"
            )

        if serial_end_requested is None:
            if serial_start_requested == serial_end_available + 1:
                # A specific message is triggered when starting from a serial
                # that is the current plus one, until LAST
                return "% Warning: there are no newer updates available"
            elif serial_start_requested > serial_end_available:
                raise NRTMGeneratorException(
                    f"Serials {serial_end_available} - {serial_start_requested} do not exist"
                )

        serial_end_display = serial_end_available if serial_end_requested is None else serial_end_requested

        range_limit = get_setting(f"sources.{source}.nrtm_query_serial_range_limit")
        if range_limit and int(range_limit) < (serial_end_display - serial_start_requested):
            raise NRTMGeneratorException(f"Serial range requested exceeds maximum range of {range_limit}")

        q = (
            RPSLDatabaseJournalQuery()
            .sources([source])
            .serial_nrtm_range(serial_start_requested, serial_end_requested)
        )

        output = [f"%START Version: {version} {source} {serial_start_requested}-{serial_end_display}\n"]

        for operation in database_handler.execute_query(q):
            operation_str = operation["operation"].value
            if version == "3":
                operation_str += " " + str(operation["serial_nrtm"])
            text = operation["object_text"]
            if remove_auth_hashes:
                text = remove_auth_hashes_func(text)
            operation_str += "\n\n" + text
            output.append(operation_str)

        output.append(f"%END {source}")
        return "\n".join(output)
