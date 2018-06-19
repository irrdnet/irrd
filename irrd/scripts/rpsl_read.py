#!/usr/bin/env python
"""
# TODO: expand pythonpath and update this description

This is a small helper script to run RPSL data through the parser.

This may be useful to validate the strictness of the parser against
live RPSL data.
"""
import argparse
import sys
from typing import Set

from irrd.db.api import DatabaseHandler
from irrd.rpsl.parser import UnknownRPSLObjectClassException
from irrd.rpsl.rpsl_objects import rpsl_object_from_text


class RPSLParse:
    obj_parsed = 0
    obj_errors = 0
    obj_unknown = 0
    unknown_object_classes: Set[str] = set()
    database_handler = None

    def main(self, filename, strict_validation, database):
        if database:
            self.database_handler = DatabaseHandler()

        if filename == '-':  # pragma: no cover
            f = sys.stdin
        else:
            f = open(filename, encoding="iso-8859-1")

        current_obj = ""
        for line in f.readlines():
            if line.startswith("%") or line.startswith("#"):
                continue
            current_obj += line

            if not line.strip("\r\n"):
                self.parse_object(current_obj, strict_validation)
                current_obj = ""

        self.parse_object(current_obj, strict_validation)

        print(f"Processed {self.obj_parsed} objects, {self.obj_errors} with errors")
        if self.obj_unknown:
            unknown_formatted = ', '.join(self.unknown_object_classes)
            print(f"Ignored {self.obj_unknown} objects due to unknown object classes: {unknown_formatted}")

        if self.database_handler:
            self.database_handler.commit()

    def parse_object(self, rpsl_text, strict_validation):
        if not rpsl_text.strip():
            return
        try:
            self.obj_parsed += 1
            obj = rpsl_object_from_text(rpsl_text.strip(), strict_validation=strict_validation)
            if obj.messages.messages():
                if obj.messages.errors():
                    self.obj_errors += 1

                print(rpsl_text.strip())
                print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
                print(obj.messages)
                print("\n=======================================\n")

            if self.database_handler and obj and not obj.messages.errors():
                self.database_handler.upsert_rpsl_object(obj)

        except UnknownRPSLObjectClassException as e:
            self.obj_unknown += 1
            self.unknown_object_classes.add(str(e).split(":")[1].strip())
        except Exception as e:  # pragma: no cover
            print("=======================================")
            print(rpsl_text)
            print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            raise e


if __name__ == "__main__":
    description = """Run RPSL data through the IRRD processor. For each object that resulted in messages emitted by
                     the parser, the object is printed followed by the messages. Optionally, insert objects into
                     the database."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("input_file", type=str,
                        help="the name of a file to read, or - for stdin")
    parser.add_argument("--strict", dest="strict_validation", action="store_true",
                        help="use strict validation (errors on e.g. unknown or missing attributes)")
    parser.add_argument("--database-destructive-overwrite", dest="database", action="store_true",
                        help="insert all valid objects into the IRRD database - OVERWRITING ANY EXISTING ENTRIES, if"
                             "they have the same RPSL primary key and source")
    args = parser.parse_args()

    RPSLParse().main(args.input_file, args.strict_validation, args.database)
