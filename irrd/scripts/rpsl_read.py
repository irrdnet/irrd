#!/usr/bin/env python
# flake8: noqa: E402
"""
This is a helper script to run RPSL data through the parser and, optionally,
insert it into the database.
"""
import argparse
import sys

from pathlib import Path
from typing import Set

from irrd.storage.models import JournalEntryOrigin

sys.path.append(str(Path(__file__).resolve().parents[2]))

from irrd.conf import CONFIG_PATH_DEFAULT, config_init, get_setting
from irrd.storage.database_handler import DatabaseHandler
from irrd.rpsl.parser import UnknownRPSLObjectClassException
from irrd.rpsl.rpsl_objects import rpsl_object_from_text
from irrd.utils.text import split_paragraphs_rpsl


class RPSLParse:
    obj_parsed = 0
    obj_errors = 0
    obj_unknown = 0
    unknown_object_classes: Set[str] = set()
    database_handler = None

    def main(self, filename, strict_validation, database, show_info=True):
        self.show_info = show_info
        if database:
            self.database_handler = DatabaseHandler()
            self.database_handler.disable_journaling()

        if filename == '-':  # pragma: no cover
            f = sys.stdin
        else:
            f = open(filename, encoding='utf-8', errors='backslashreplace')

        for paragraph in split_paragraphs_rpsl(f):
            self.parse_object(paragraph, strict_validation)

        print(f'Processed {self.obj_parsed} objects, {self.obj_errors} with errors')
        if self.obj_unknown:
            unknown_formatted = ', '.join(self.unknown_object_classes)
            print(f'Ignored {self.obj_unknown} objects due to unknown object classes: {unknown_formatted}')

        if self.database_handler:
            self.database_handler.commit()
            self.database_handler.close()

    def parse_object(self, rpsl_text, strict_validation):
        try:
            self.obj_parsed += 1
            obj = rpsl_object_from_text(rpsl_text.strip(), strict_validation=strict_validation)
            if (obj.messages.messages() and self.show_info) or obj.messages.errors():
                if obj.messages.errors():
                    self.obj_errors += 1

                print(rpsl_text.strip())
                print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')
                print(obj.messages)
                print('\n=======================================\n')

            if self.database_handler and obj and not obj.messages.errors():
                self.database_handler.upsert_rpsl_object(obj, JournalEntryOrigin.mirror)

        except UnknownRPSLObjectClassException as e:
            self.obj_unknown += 1
            self.unknown_object_classes.add(str(e).split(':')[1].strip())
        except Exception as e:  # pragma: no cover
            print('=======================================')
            print(rpsl_text)
            print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')
            raise e


def main():  # pragma: no cover
    description = """Run RPSL data through the IRRD processor. For each object that resulted in messages emitted by
                     the parser, the object is printed followed by the messages. Optionally, insert objects into
                     the database."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--config', dest='config_file_path', type=str,
                        help=f'use a different IRRd config file (default: {CONFIG_PATH_DEFAULT})')
    parser.add_argument('--hide-info', dest='hide_info', action='store_true',
                        help='hide INFO messages')
    parser.add_argument('--strict', dest='strict_validation', action='store_true',
                        help='use strict validation (errors on e.g. unknown or missing attributes)')
    parser.add_argument('--database-destructive-overwrite', dest='database', action='store_true',
                        help='insert all valid objects into the IRRD database - OVERWRITING ANY EXISTING ENTRIES, if '
                             'they have the same RPSL primary key and source')
    parser.add_argument('input_file', type=str,
                        help='the name of a file to read, or - for stdin')
    args = parser.parse_args()

    config_init(args.config_file_path)
    if get_setting('database_readonly'):
        print('Unable to run, because database_readonly is set')
        sys.exit(-1)
        
    RPSLParse().main(args.input_file, args.strict_validation, args.database, not args.hide_info)


if __name__ == '__main__':
    main()
