#!/usr/bin/env python
"""
This is a small helper script to run RPSL data through the parser.

This may be useful to validate the strictness of the parser against
live RPSL data.
"""
import argparse
import sys

from irrd.rpsl.parser import UnknownRPSLObjectClassException
from irrd.rpsl.rpsl_objects import rpsl_object_from_text
from irrd.db.tables import RPSLDatabaseObjectWriter

obj_parsed = 0
obj_errors = 0
obj_unknown = 0
unknown_object_classes = set()
database_writer = None


def parse(rpsl_text, strict_validation):
    global obj_parsed
    global obj_errors
    global obj_unknown
    global records
    global database_writer

    if not rpsl_text.strip():
        return
    try:
        obj_parsed += 1
        obj = rpsl_object_from_text(rpsl_text.strip(), strict_validation=strict_validation)
        if obj.messages.messages():
            if obj.messages.errors():
                obj_errors += 1
        if obj and not obj.messages.errors():
            database_writer.add_object(obj)

            # print(rpsl_text.strip())
            # print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            # print(obj.messages)
            # print("\n=======================================\n")
    except UnknownRPSLObjectClassException as e:
        obj_unknown += 1
        unknown_object_classes.add(str(e).split(":")[1].strip())
    # except IntegrityError as e:
    #     print("=======================================")
    #     print(rpsl_text)
    #     print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
    #     print(e)
    #     session.rollback()
    except Exception as e:  # pragma: no cover
        print("=======================================")
        print(rpsl_text)
        print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        raise e


def main(filename, strict_validation):
    global obj_parsed
    global obj_errors
    global obj_unknown
    global unknown_object_classes
    global database_writer

    obj_parsed = 0
    obj_errors = 0
    obj_unknown = 0
    unknown_object_classes = set()

    if filename == '-':  # pragma: no cover
        f = sys.stdin
    else:
        f = open(filename, encoding="iso-8859-1")

    database_writer = RPSLDatabaseObjectWriter()
    current_obj = ""
    for line in f.readlines():
        if line.startswith("%") or line.startswith("#"):
            continue
        current_obj += line

        if not line.strip("\r\n"):
            parse(current_obj, strict_validation)
            current_obj = ""

    parse(current_obj, strict_validation)

    print(f"Processed {obj_parsed} objects, {obj_errors} with errors")
    if obj_unknown:
        unknown_formatted = ', '.join(unknown_object_classes)
        print(f"Ignored {obj_unknown} objects due to unknown object classes: {unknown_formatted}")

    database_writer.commit()


if __name__ == "__main__":
    description = """Run RPSL data through the IRRD parser. For each object that resulted in messages emitted by
                     the parser, the object is printed followed by the messages."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("input_file", type=str,
                        help="the name of a file to read, or - for stdin")
    parser.add_argument("--strict", dest="strict_validation", action="store_true",
                        help="use strict validation (errors on e.g. unknown or missing attributes)")
    args = parser.parse_args()

    main(args.input_file, args.strict_validation)
