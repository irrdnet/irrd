import logging
import os
from typing import Optional

from irrd.conf import RPKI_IRR_PSEUDO_SOURCE, get_setting
from irrd.conf.defaults import DEFAULT_SOURCE_NRTM_PORT
from irrd.mirroring.nrtm4.nrtm4_client import NRTM4Client, NRTM4ClientError
from irrd.routepref.routepref import update_route_preference_status
from irrd.rpki.importer import ROADataImporter, ROAParserException
from irrd.rpki.notifications import notify_rpki_invalid_owners
from irrd.rpki.validators import BulkRouteROAValidator
from irrd.scopefilter.validators import ScopeFilterValidator
from irrd.storage.database_handler import DatabaseHandler
from irrd.storage.event_stream import EventStreamPublisher
from irrd.storage.queries import DatabaseStatusQuery
from irrd.utils.whois_client import whois_query

from .parsers import MirrorFileImportParser, NRTMStreamParser
from .retrieval import retrieve_file

logger = logging.getLogger(__name__)


class RPSLMirrorImportUpdateRunner:
    """
    This RPSLMirrorImportUpdateRunner is the entry point for updating a single
    database mirror, depending on current state.

    For NRTMv4, it will call the NRTM 4 client which handles snapshot/delta
    loading internally.
    If there is no current mirrored data, will call RPSLMirrorFullImportRunner
    to run a new import from full export files. Otherwise, will call
    NRTMImportUpdateStreamRunner to retrieve new updates from NRTM.
    """

    def __init__(self, source: str) -> None:
        self.source = source
        self.full_import_runner = RPSLMirrorFullImportRunner(source)
        self.update_stream_runner = NRTMImportUpdateStreamRunner(source)

    def run(self) -> None:
        self.database_handler = DatabaseHandler()

        try:
            if get_setting(f"sources.{self.source}.nrtm4_client_notification_file_url"):
                full_reload = NRTM4Client(
                    source=self.source, database_handler=self.database_handler
                ).run_client()
            else:
                full_reload = self.run_full_or_nrtm3_import()

            self.database_handler.commit()
            if full_reload:
                event_stream_publisher = EventStreamPublisher()
                event_stream_publisher.publish_rpsl_full_reload(self.source)
                event_stream_publisher.close()

        except NRTM4ClientError as err:
            msg = (
                f"{self.source}: Validation errors occurred while attempting a NRTMv4 client update:"
                f" {str(err)}"
            )
            logger.error(msg)
            self.database_handler.record_mirror_error(self.source, str(err))
        except OSError as ose:
            # I/O errors can occur and should not log a full traceback (#177)
            logger.error(
                "An error occurred while attempting a mirror update or initial import "
                f"for {self.source}: {ose}"
            )
        except Exception as exc:
            logger.error(
                "An exception occurred while attempting a mirror update or initial import "
                f"for {self.source}: {exc}",
                exc_info=exc,
            )
        finally:
            self.database_handler.close()

    def run_full_or_nrtm3_import(self):
        serial_newest_mirror, force_reload = self._status()
        nrtm_enabled = bool(get_setting(f"sources.{self.source}.nrtm_host"))
        logger.debug(
            f"Most recent mirrored serial for {self.source}: {serial_newest_mirror}, "
            f"force_reload: {force_reload}, nrtm enabled: {nrtm_enabled}"
        )
        full_reload = force_reload or not serial_newest_mirror or not nrtm_enabled
        if full_reload:
            self.full_import_runner.run(
                database_handler=self.database_handler,
                serial_newest_mirror=serial_newest_mirror,
                force_reload=force_reload,
            )
        else:
            assert serial_newest_mirror
            self.update_stream_runner.run(serial_newest_mirror, database_handler=self.database_handler)
        return full_reload

    def _status(self) -> tuple[Optional[int], Optional[bool]]:
        query = DatabaseStatusQuery().source(self.source)
        result = self.database_handler.execute_query(query)
        try:
            status = next(result)
            return status["serial_newest_mirror"], status["force_reload"]
        except StopIteration:
            return None, None


class RPSLMirrorFullImportRunner:
    """
    This runner performs a full import from database exports for a single
    mirrored source. URLs for full export file(s), and the URL for the serial
    they match, are provided in configuration.

    Files are downloaded, gunzipped if needed, and then sent through the
    MirrorFileImportParser.
    """

    def __init__(self, source: str) -> None:
        self.source = source

    def run(
        self,
        database_handler: DatabaseHandler,
        serial_newest_mirror: Optional[int] = None,
        force_reload=False,
    ):
        import_sources = get_setting(f"sources.{self.source}.import_source")
        if isinstance(import_sources, str):
            import_sources = [import_sources]
        import_serial_source = get_setting(f"sources.{self.source}.import_serial_source")

        if not import_sources:
            logger.info(f"Skipping full RPSL import for {self.source}, import_source not set.")
            return

        logger.info(
            f"Running full RPSL import of {self.source} from {import_sources}, serial from"
            f" {import_serial_source}"
        )

        import_serial = None
        if import_serial_source:
            import_serial = int(retrieve_file(import_serial_source, return_contents=True)[0])

            if (
                not force_reload
                and serial_newest_mirror is not None
                and import_serial <= serial_newest_mirror
            ):
                logger.info(
                    f"Current newest serial seen from mirror for {self.source} is "
                    f"{serial_newest_mirror}, import_serial is {import_serial}, cancelling import."
                )
                return

        database_handler.delete_all_rpsl_objects_with_journal(self.source)
        import_data = [
            retrieve_file(import_source, return_contents=False) for import_source in import_sources
        ]

        roa_validator = None
        if get_setting("rpki.roa_source"):
            roa_validator = BulkRouteROAValidator(database_handler)

        database_handler.disable_journaling()
        for import_filename, to_delete in import_data:
            p = MirrorFileImportParser(
                source=self.source,
                filename=import_filename,
                serial=None,
                database_handler=database_handler,
                roa_validator=roa_validator,
            )
            try:
                p.run_import()
            finally:
                if to_delete:
                    os.unlink(import_filename)

        if import_serial:
            database_handler.record_serial_newest_mirror(self.source, import_serial)


class ROAImportRunner:
    """
    This runner performs a full import of ROA objects.
    The URL file for the ROA export in JSON format is provided
    in the configuration.
    """

    def run(self):
        self.database_handler = DatabaseHandler()

        try:
            self.database_handler.disable_journaling()
            roa_objs = self._import_roas()
            # Do an early commit to make the new ROAs available to other processes.
            self.database_handler.commit()
            # The ROA import does not use journaling, but updating the RPKI
            # status may create journal entries.
            self.database_handler.enable_journaling()

            validator = BulkRouteROAValidator(self.database_handler, roa_objs)
            objs_now_valid, objs_now_invalid, objs_now_not_found = validator.validate_all_routes()
            self.database_handler.update_rpki_status(
                rpsl_objs_now_valid=objs_now_valid,
                rpsl_objs_now_invalid=objs_now_invalid,
                rpsl_objs_now_not_found=objs_now_not_found,
            )
            self.database_handler.commit()
            notified = notify_rpki_invalid_owners(self.database_handler, objs_now_invalid)
            logger.info(
                f"RPKI status updated for all routes, {len(objs_now_valid)} newly valid, "
                f"{len(objs_now_invalid)} newly invalid, "
                f"{len(objs_now_not_found)} newly not_found routes, "
                f"{notified} emails sent to contacts of newly invalid authoritative objects"
            )

        except OSError as ose:
            # I/O errors can occur and should not log a full traceback (#177)
            logger.error(f"An error occurred while attempting a ROA import: {ose}")
        except ROAParserException as rpe:
            logger.error(f"An exception occurred while attempting a ROA import: {rpe}")
        except Exception as exc:
            logger.error(f"An exception occurred while attempting a ROA import: {exc}", exc_info=exc)
        finally:
            self.database_handler.close()

    def _import_roas(self):
        roa_source = get_setting("rpki.roa_source")
        slurm_source = get_setting("rpki.slurm_source")
        logger.info(f"Running full ROA import from: {roa_source}, SLURM {slurm_source}")

        self.database_handler.delete_all_roa_objects()
        self.database_handler.delete_all_rpsl_objects_with_journal(
            RPKI_IRR_PSEUDO_SOURCE,
            journal_guaranteed_empty=True,
        )

        slurm_data = None
        if slurm_source:
            slurm_data, _ = retrieve_file(slurm_source, return_contents=True)

        roa_filename, roa_to_delete = retrieve_file(roa_source, return_contents=False)
        with open(roa_filename) as fh:
            roa_importer = ROADataImporter(fh.read(), slurm_data, self.database_handler)
        if roa_to_delete:
            os.unlink(roa_filename)
        logger.info(
            f"ROA import from {roa_source}, SLURM {slurm_source}, imported {len(roa_importer.roa_objs)} ROAs,"
            " running validator"
        )
        return roa_importer.roa_objs


class ScopeFilterUpdateRunner:
    """
    Update the scope filter status for all objects.
    This runner does not actually import anything, the scope filter
    is in the configuration.
    """

    def run(self):
        self.database_handler = DatabaseHandler()

        try:
            validator = ScopeFilterValidator()
            status = validator.validate_all_rpsl_objects(self.database_handler)
            rpsl_objs_now_in_scope, rpsl_objs_now_out_scope_as, rpsl_objs_now_out_scope_prefix = status
            self.database_handler.update_scopefilter_status(
                rpsl_objs_now_in_scope=rpsl_objs_now_in_scope,
                rpsl_objs_now_out_scope_as=rpsl_objs_now_out_scope_as,
                rpsl_objs_now_out_scope_prefix=rpsl_objs_now_out_scope_prefix,
            )
            self.database_handler.commit()
            logger.info(
                "Scopefilter status updated for all routes, "
                f"{len(rpsl_objs_now_in_scope)} newly in scope, "
                f"{len(rpsl_objs_now_out_scope_as)} newly out of scope AS, "
                f"{len(rpsl_objs_now_out_scope_prefix)} newly out of scope prefix"
            )

        except Exception as exc:
            logger.error(
                f"An exception occurred while attempting a scopefilter status update: {exc}", exc_info=exc
            )
        finally:
            self.database_handler.close()


class RoutePreferenceUpdateRunner:
    """
    Update the route preference filter status for all objects.
    This runner does not actually import anything external, all
    data is already in our database.
    """

    # API consistency with other importers, source is actually ignored
    def __init__(self, source=None):
        pass

    def run(self):
        database_handler = DatabaseHandler()

        try:
            update_route_preference_status(database_handler)
            database_handler.commit()
            logger.info("route preference update commit complete")
        except Exception as exc:
            logger.error(
                f"An exception occurred while attempting a route preference status update: {exc}",
                exc_info=exc,
            )
        finally:
            database_handler.close()


class NRTMImportUpdateStreamRunner:
    """
    This runner attempts to pull updates from an NRTM stream for a specific
    mirrored database.
    """

    def __init__(self, source: str) -> None:
        self.source = source

    def run(self, serial_newest_mirror: int, database_handler: DatabaseHandler):
        serial_start = serial_newest_mirror + 1
        nrtm_host = get_setting(f"sources.{self.source}.nrtm_host")
        nrtm_port = int(get_setting(f"sources.{self.source}.nrtm_port", DEFAULT_SOURCE_NRTM_PORT))
        if not nrtm_host:
            logger.debug(f"Skipping NRTM updates for {self.source}, nrtm_host not set.")
            return

        end_markings = [
            f"\n%END {self.source}\n",
            f"\n% END {self.source}\n",
            "\n%ERROR",
            "\n% ERROR",
            "\n% Warning: there are no newer updates available",
            "\n% Warning (1): there are no newer updates available",
        ]

        logger.info(
            f"Retrieving NRTM updates for {self.source} from serial {serial_start} on {nrtm_host}:{nrtm_port}"
        )
        query = f"-g {self.source}:3:{serial_start}-LAST"
        response = whois_query(nrtm_host, nrtm_port, query, end_markings)
        logger.debug(f"Received NRTM response for {self.source}: {response.strip()}")

        stream_parser = NRTMStreamParser(self.source, response, database_handler)
        for operation in stream_parser.operations:
            operation.save(database_handler)
