import sys

from .rpsl_objects import rpsl_object_from_text

if sys.argv[1]:
    f = open(sys.argv[1], encoding="iso-8859-1")
else:
    f = sys.stdin

obj_parsed = 0
obj_errors = 0


def parse(rpsl_text):
    global obj_parsed
    global obj_errors
    if not rpsl_text.strip():
        return
    try:
        obj_parsed += 1
        obj = rpsl_object_from_text(rpsl_text.strip(), True)
        if obj.messages.messages():
            obj_errors += 1
            # print(current_obj.strip())
            # print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            # print(obj.messages)
            # print("\n=======================================\n")

    except Exception as e:
        print("=======================================")
        print(input)
        print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        raise e


current_obj = ""
for line in f.readlines():
    if line.startswith("%") or line.startswith("#"):
        continue
    current_obj += line

    if not line.strip("\r\n"):
        parse(current_obj)
        current_obj = ""

parse(current_obj)


print(f"Processed {obj_parsed} objects, {obj_errors} with errors")
