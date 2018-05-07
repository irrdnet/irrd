#!/bin/bash -x
# This is a simple script to run our tests in parallel on CircleCI. This will be called from circle.yml.
# At this time, the script only works for having two nodes.

ret=0

case $CIRCLE_NODE_INDEX in
    0)
    flake8 irrd || ret=$?
    mypy irrd --ignore-missing-imports || ret=$?
    ;;

    1)
    # TODO: increase coverage requirement
    py.test --cov=irrd irrd || ret=$?
    ;;
esac

exit $ret



