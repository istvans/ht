# coding=utf-8
"""Common code shared across the project"""
import argparse
import contextlib
import sys
import traceback


READ_ONLY_ARG = "read_only"
PAUSE_ARG = "pause"


class UserInputWasCancelled(Exception):
    """Should be raised when the user cancels an interactive input session"""


def cli_arg_parser():
    """Return the argparser instance with the common CLI parameters"""
    parser = argparse.ArgumentParser(
        description="Let me help you with that repetitive stuff..."
    )
    parser.add_argument("-s", "--spreadsheet", required=True,
                        help="the spreadsheet to be used as our database")
    parser.add_argument("-c", "--currency", required=False, help="the currency HT uses",
                        default="eFt")
    parser.add_argument("-u", "--user", required=False, help="the hattrick user")
    parser.add_argument("-p", "--password", required=False, help="the hattrick password")
    parser.add_argument("-P", "--{}".format(PAUSE_ARG), required=False,
                        help="pause the script at the end", action='store_true')
    parser.add_argument("-r", "--{}".format(READ_ONLY_ARG), required=False,
                        help="run in read-only persistence layer mode",
                        action="store_true")
    return parser


@contextlib.contextmanager
def maybe_pause_at_the_end(pause):
    """pause at the end if `pause` is True"""
    try:
        yield
    finally:
        if pause:
            (exc_type, exc, trace) = sys.exc_info()
            if exc is not None:
                traceback.print_exception(exc_type, exc, trace)
            input("Press Enter to continue...")


def get_from_user(named_thing, parse_from_string, choices):
    """Try to get the named thing as the result of `parse_from_string` from the user
    """
    value = None
    choices_in_parentheses = choices if isinstance(choices, tuple) else "({})".format(choices)
    prompt = "{} {}: ".format(named_thing, choices_in_parentheses)
    while value is None:
        try:
            value = input(prompt)
        except KeyboardInterrupt:
            raise UserInputWasCancelled() from None
        try:
            value = parse_from_string(value)
        except (TypeError, ValueError):
            value = None
        if value is None:
            print("Please specify a valid '{}' (or hit ctrl+c)".format(named_thing))
    return value
