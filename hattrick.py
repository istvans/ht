# coding=utf-8
"""My little Hattrick scraper module
"""
import io
import re
import requests
import sys

from getpass import getpass
from pprint import pprint

from data import Player, Age, NationalPlayerStatus, Team


class NoDefinitionInThisLanguageError(Exception):
    """Should be raised if we try to get the translation for a supported language
    in LanguageDependentText, but it is None
    """
    pass


class LanguageDependentText(object):
    """Store all the translations of a text in these 'language fields'"""

    SUPPORTED_LANGUAGES = ["hungarian", "english"]

    def __init__(self, **kwargs):
        for language in self.SUPPORTED_LANGUAGES:
            setattr(self, language, kwargs[language])

    def translate_to(self, language):
        """Get the text in the specified language
        If the language is not supported -> AttributeError
        If the language is supported, but the text is None -> NoDefinitionInThisLanguageError
        """
        text = getattr(self, language)
        if text is None:
            available_definitions = {
                language: value
                for language in dir(self)
                if not language.startswith('__')
                   and (value := getattr(self, language)) is not None
            }
            raise NoDefinitionInThisLanguageError(
                "{} available definitions: {}".format(language, available_definitions))
        return text


def _raise_and_try_dumping_page_error(base_error_message, dump_suffix, page, regex=None):
    """Raise a runtime error and try to dump the `page` to crashdump.`dump_suffix`.html
    `base_error_message` will be extended with (the optional) `regex` and the
    dump file name if dumping succeeded
    """
    saved_page_file = "crashdump.{}.html".format(dump_suffix)
    try:
        _dump_a_page_to_file(page, saved_page_file)
    except Exception:
        saved_page_file = None

    if regex is not None:
        error_message = "{} regex: '{}'".format(base_error_message, regex)
    else:
        error_message = base_error_message

    if saved_page_file is not None:
        error_message = (("{} this page dump might help: '{}'")
                         .format(error_message, saved_page_file))

    raise RuntimeError(error_message)


def _remove_witespace(raw_string):
    """Return a new string without any whitespace"""
    return "".join(raw_string.split())


def _string_to_int(raw_string):
    """Convert a string that contain numbers and optionally whitespace to int"""
    return int(_remove_witespace(raw_string))


def _dump_a_page_to_file(page, file_name):
    """Dump the text of `page` into `file_name`
    It might raise all kinds of io errors...
    """
    with io.open(file_name, mode="w", encoding="utf-8") as dump_file:
        dump_file.write(page.text)


def _bytes_to_string(bytes_value):
    r"""Convert `bytes_value` to string by also replacing the following HTML characters
    \xa0 -> " "
    &nbsp; -> " "
    """
    return bytes_value.decode("utf-8").replace(u"\xa0", u" ").replace(u"&nbsp;", u" ")


class FindState(object):
    """Preserve state for a find algorithm with multiple phases"""
    def __init__(self):
        self.lets_find = False
        self.found_value = None

    def found(self):
        """Return if the searched value was found"""
        return self.found_value is not None

    def get_int_or_raise_and_try_dumping_page_error(self, base_error_message, dump_suffix,
                                                    page, regex=None):
        """As its name suggests: it tries to return the `found_value` as `int`, or
        if it wasn't found, call _raise_and_try_dumping_page_error()
        If converting the found value to `int` fails, some kind of exception will
        be raised too
        """
        if self.found():
            int_value = _string_to_int(self.found_value)
        else:
            self._raise_and_try_dumping_page_error(base_error_message, dump_suffix,
                                                   page, regex)
        return int_value


def _find_after_a_start_match(start_pattern, value_pattern, text, find_state):
    """Find the `start_pattern` then look for the `value_pattern` and, once found,
    save it into `find_state`
    """
    if not isinstance(find_state, FindState):
        raise TypeError("find_state must be of type FindState and not '{}'"
                        .format(type(find_state)))

    if find_state.lets_find and find_state.found_value is None:
            if match := re.search(value_pattern, text):
                find_state.found_value = match.group("value")

    if find_state.found_value is None and re.search(start_pattern, text):
        find_state.lets_find = True


class Hattrick(object):
    """Represent a Hattrick login sesion"""

    MAIN_PAGE = "https://www.hattrick.org/en/"

    LOGIN_PAGE = "https://www.hattrick.org/en/Startpage3.aspx"

    HEADER = {"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36"}

    EVENT_VALIDATION_KEY = "__EVENTVALIDATION"
    VIEW_STATE_KEY = "__VIEWSTATE"
    VIEW_STATE_GENERATOR_KEY = "__VIEWSTATEGENERATOR"

    TOKEN = ";;System.Web.Extensions, Version=4.0.0.0, Culture=neutral, PublicKeyToken=31bf3856ad364e35:en-GB:ad6c4949-7f20-401f-a40f-4d4c52722104:ea597d4b:b25378d2"

    LOGIN_FORM = {
        "ctl00_sm_HiddenField": TOKEN,
        "__EVENTTARGET": "ctl00$CPContent$ucLogin$butLogin",
        VIEW_STATE_KEY: "/wEPDwUJNDQyOTQ2ODUyD2QWAmYPZBYEZg9kFhICAQ8WAh4EaHJlZgUcaHR0cHM6Ly93d3cuaGF0dHJpY2sub3JnL2VuL2QCAw8WAh4HQ29udGVudAV/VGhlIG9yaWdpbmFsIGFuZCB0aGUgbW9zdCBwb3B1bGFyIG9ubGluZSBmb290YmFsbCBtYW5hZ2VyIGdhbWUuIEl0J3MgZnJlZSB0byBwbGF5IC0gZXZlcnlib2R5IGRlc2VydmVzIHRoZWlyIG93biBmb290YmFsbCB0ZWFtIWQCBg8WAh4EVGV4dAUzPG1ldGEgaHR0cC1lcXVpdj0nQ29udGVudC1MYW5ndWFnZScgY29udGVudD0nZW4nIC8+ZAIHDxYCHwAFKS92MjAwOTQxMC9BcHBfVGhlbWVzL1N0YW5kYXJkX21haW5fMTEuY3NzZAIJDxYCHwIF8gE8c2NyaXB0IGFzeW5jIHNyYz0iaHR0cHM6Ly93d3cuZ29vZ2xldGFnbWFuYWdlci5jb20vZ3RhZy9qcz9pZD1BVy03ODMwNDQ0OTMiPjwvc2NyaXB0PjxzY3JpcHQ+d2luZG93LmRhdGFMYXllciA9IHdpbmRvdy5kYXRhTGF5ZXIgfHwgW107ZnVuY3Rpb24gZ3RhZygpe2RhdGFMYXllci5wdXNoKGFyZ3VtZW50cyk7fWd0YWcoJ2pzJywgbmV3IERhdGUoKSk7Z3RhZygnY29uZmlnJywgJ0FXLTc4MzA0NDQ5MycpOzwvc2NyaXB0PmQCCg8WAh8CBdoBPHNjcmlwdCB0eXBlPSJ0ZXh0L2phdmFzY3JpcHQiPnZhciBfZ2FxID0gX2dhcSB8fCBbXTtfZ2FxLnB1c2goWydfc2V0QWNjb3VudCcsICdVQS02NTYyODY2LTEnXSk7X2dhcS5wdXNoKFsnX3NldERvbWFpbk5hbWUnLCAnLmhhdHRyaWNrLm9yZyddKTtfZ2FxLnB1c2goWydfc2V0QWxsb3dIYXNoJywgZmFsc2VdKTtfZ2FxLnB1c2goWydfdHJhY2tQYWdldmlldyddKTs8L3NjcmlwdD5kAgsPFgIfAgUsPG1ldGEgbmFtZT0icm9ib3RzIiBjb250ZW50PSJpbmRleCxmb2xsb3ciLz5kAgwPFgIfAgWCITxsaW5rIHJlbD0iYWx0ZXJuYXRlIiBocmVmbGFuZz0ieC1kZWZhdWx0IiBocmVmPSJodHRwczovL3d3dy5oYXR0cmljay5vcmcvIiAvPg0KPGxpbmsgcmVsPSJhbHRlcm5hdGUiIGhyZWZsYW5nPSJzcSIgaHJlZj0iaHR0cHM6Ly93d3cuaGF0dHJpY2sub3JnL3NxLyIgLz4NCjxsaW5rIHJlbD0iYWx0ZXJuYXRlIiBocmVmbGFuZz0iYXIiIGhyZWY9Imh0dHBzOi8vd3d3LmhhdHRyaWNrLm9yZy9hci8iIC8+DQo8bGluayByZWw9ImFsdGVybmF0ZSIgaHJlZmxhbmc9ImF6IiBocmVmPSJodHRwczovL3d3dy5oYXR0cmljay5vcmcvYXovIiAvPg0KPGxpbmsgcmVsPSJhbHRlcm5hdGUiIGhyZWZsYW5nPSJpZCIgaHJlZj0iaHR0cHM6Ly93d3cuaGF0dHJpY2sub3JnL2lkLyIgLz4NCjxsaW5rIHJlbD0iYWx0ZXJuYXRlIiBocmVmbGFuZz0iYnMiIGhyZWY9Imh0dHBzOi8vd3d3LmhhdHRyaWNrLm9yZy9icy8iIC8+DQo8bGluayByZWw9ImFsdGVybmF0ZSIgaHJlZmxhbmc9ImJnIiBocmVmPSJodHRwczovL3d3dy5oYXR0cmljay5vcmcvYmcvIiAvPg0KPGxpbmsgcmVsPSJhbHRlcm5hdGUiIGhyZWZsYW5nPSJjYSIgaHJlZj0iaHR0cHM6Ly93d3cuaGF0dHJpY2sub3JnL2NhLyIgLz4NCjxsaW5rIHJlbD0iYWx0ZXJuYXRlIiBocmVmbGFuZz0iY3MiIGhyZWY9Imh0dHBzOi8vd3d3LmhhdHRyaWNrLm9yZy9jcy8iIC8+DQo8bGluayByZWw9ImFsdGVybmF0ZSIgaHJlZmxhbmc9ImRhIiBocmVmPSJodHRwczovL3d3dy5oYXR0cmljay5vcmcvZGEvIiAvPg0KPGxpbmsgcmVsPSJhbHRlcm5hdGUiIGhyZWZsYW5nPSJkZSIgaHJlZj0iaHR0cHM6Ly93d3cuaGF0dHJpY2sub3JnL2RlLyIgLz4NCjxsaW5rIHJlbD0iYWx0ZXJuYXRlIiBocmVmbGFuZz0iZXQiIGhyZWY9Imh0dHBzOi8vd3d3LmhhdHRyaWNrLm9yZy9ldC8iIC8+DQo8bGluayByZWw9ImFsdGVybmF0ZSIgaHJlZmxhbmc9ImVuIiBocmVmPSJodHRwczovL3d3dy5oYXR0cmljay5vcmcvZW4vIiAvPg0KPGxpbmsgcmVsPSJhbHRlcm5hdGUiIGhyZWZsYW5nPSJlbi11cyIgaHJlZj0iaHR0cHM6Ly93d3cuaGF0dHJpY2sub3JnL2VuLXVzLyIgLz4NCjxsaW5rIHJlbD0iYWx0ZXJuYXRlIiBocmVmbGFuZz0iZXMiIGhyZWY9Imh0dHBzOi8vd3d3LmhhdHRyaWNrLm9yZy9lcy8iIC8+DQo8bGluayByZWw9ImFsdGVybmF0ZSIgaHJlZmxhbmc9ImVzLW14IiBocmVmPSJodHRwczovL3d3dy5oYXR0cmljay5vcmcvZXMtbXgvIiAvPg0KPGxpbmsgcmVsPSJhbHRlcm5hdGUiIGhyZWZsYW5nPSJlcy1hciIgaHJlZj0iaHR0cHM6Ly93d3cuaGF0dHJpY2sub3JnL2VzLWFyLyIgLz4NCjxsaW5rIHJlbD0iYWx0ZXJuYXRlIiBocmVmbGFuZz0iZXUiIGhyZWY9Imh0dHBzOi8vd3d3LmhhdHRyaWNrLm9yZy9ldS8iIC8+DQo8bGluayByZWw9ImFsdGVybmF0ZSIgaHJlZmxhbmc9ImZyIiBocmVmPSJodHRwczovL3d3dy5oYXR0cmljay5vcmcvZnIvIiAvPg0KPGxpbmsgcmVsPSJhbHRlcm5hdGUiIGhyZWZsYW5nPSJmeSIgaHJlZj0iaHR0cHM6Ly93d3cuaGF0dHJpY2sub3JnL2Z5LyIgLz4NCjxsaW5rIHJlbD0iYWx0ZXJuYXRlIiBocmVmbGFuZz0iaXQtaXQiIGhyZWY9Imh0dHBzOi8vd3d3LmhhdHRyaWNrLm9yZy9pdC1pdC8iIC8+DQo8bGluayByZWw9ImFsdGVybmF0ZSIgaHJlZmxhbmc9ImdsIiBocmVmPSJodHRwczovL3d3dy5oYXR0cmljay5vcmcvZ2wvIiAvPg0KPGxpbmsgcmVsPSJhbHRlcm5hdGUiIGhyZWZsYW5nPSJrYSIgaHJlZj0iaHR0cHM6Ly93d3cuaGF0dHJpY2sub3JnL2thLyIgLz4NCjxsaW5rIHJlbD0iYWx0ZXJuYXRlIiBocmVmbGFuZz0iaGUiIGhyZWY9Imh0dHBzOi8vd3d3LmhhdHRyaWNrLm9yZy9oZS8iIC8+DQo8bGluayByZWw9ImFsdGVybmF0ZSIgaHJlZmxhbmc9ImhyIiBocmVmPSJodHRwczovL3d3dy5oYXR0cmljay5vcmcvaHIvIiAvPg0KPGxpbmsgcmVsPSJhbHRlcm5hdGUiIGhyZWZsYW5nPSJpcyIgaHJlZj0iaHR0cHM6Ly93d3cuaGF0dHJpY2sub3JnL2lzLyIgLz4NCjxsaW5rIHJlbD0iYWx0ZXJuYXRlIiBocmVmbGFuZz0iaXQiIGhyZWY9Imh0dHBzOi8vd3d3LmhhdHRyaWNrLm9yZy9pdC8iIC8+DQo8bGluayByZWw9ImFsdGVybmF0ZSIgaHJlZmxhbmc9Imx2IiBocmVmPSJodHRwczovL3d3dy5oYXR0cmljay5vcmcvbHYvIiAvPg0KPGxpbmsgcmVsPSJhbHRlcm5hdGUiIGhyZWZsYW5nPSJsYiIgaHJlZj0iaHR0cHM6Ly93d3cuaGF0dHJpY2sub3JnL2xiLyIgLz4NCjxsaW5rIHJlbD0iYWx0ZXJuYXRlIiBocmVmbGFuZz0ibHQiIGhyZWY9Imh0dHBzOi8vd3d3LmhhdHRyaWNrLm9yZy9sdC8iIC8+DQo8bGluayByZWw9ImFsdGVybmF0ZSIgaHJlZmxhbmc9Imh1IiBocmVmPSJodHRwczovL3d3dy5oYXR0cmljay5vcmcvaHUvIiAvPg0KPGxpbmsgcmVsPSJhbHRlcm5hdGUiIGhyZWZsYW5nPSJubCIgaHJlZj0iaHR0cHM6Ly93d3cuaGF0dHJpY2sub3JnL25sLyIgLz4NCjxsaW5rIHJlbD0iYWx0ZXJuYXRlIiBocmVmbGFuZz0ibm4iIGhyZWY9Imh0dHBzOi8vd3d3LmhhdHRyaWNrLm9yZy9ubi8iIC8+DQo8bGluayByZWw9ImFsdGVybmF0ZSIgaHJlZmxhbmc9Im5uLW5vIiBocmVmPSJodHRwczovL3d3dy5oYXR0cmljay5vcmcvbm4tbm8vIiAvPg0KPGxpbmsgcmVsPSJhbHRlcm5hdGUiIGhyZWZsYW5nPSJmYSIgaHJlZj0iaHR0cHM6Ly93d3cuaGF0dHJpY2sub3JnL2ZhLyIgLz4NCjxsaW5rIHJlbD0iYWx0ZXJuYXRlIiBocmVmbGFuZz0icGwiIGhyZWY9Imh0dHBzOi8vd3d3LmhhdHRyaWNrLm9yZy9wbC8iIC8+DQo8bGluayByZWw9ImFsdGVybmF0ZSIgaHJlZmxhbmc9InB0IiBocmVmPSJodHRwczovL3d3dy5oYXR0cmljay5vcmcvcHQvIiAvPg0KPGxpbmsgcmVsPSJhbHRlcm5hdGUiIGhyZWZsYW5nPSJwdC1iciIgaHJlZj0iaHR0cHM6Ly93d3cuaGF0dHJpY2sub3JnL3B0LWJyLyIgLz4NCjxsaW5rIHJlbD0iYWx0ZXJuYXRlIiBocmVmbGFuZz0icm8iIGhyZWY9Imh0dHBzOi8vd3d3LmhhdHRyaWNrLm9yZy9yby8iIC8+DQo8bGluayByZWw9ImFsdGVybmF0ZSIgaHJlZmxhbmc9InNrIiBocmVmPSJodHRwczovL3d3dy5oYXR0cmljay5vcmcvc2svIiAvPg0KPGxpbmsgcmVsPSJhbHRlcm5hdGUiIGhyZWZsYW5nPSJzbCIgaHJlZj0iaHR0cHM6Ly93d3cuaGF0dHJpY2sub3JnL3NsLyIgLz4NCjxsaW5rIHJlbD0iYWx0ZXJuYXRlIiBocmVmbGFuZz0iZmkiIGhyZWY9Imh0dHBzOi8vd3d3LmhhdHRyaWNrLm9yZy9maS8iIC8+DQo8bGluayByZWw9ImFsdGVybmF0ZSIgaHJlZmxhbmc9InN2IiBocmVmPSJodHRwczovL3d3dy5oYXR0cmljay5vcmcvc3YvIiAvPg0KPGxpbmsgcmVsPSJhbHRlcm5hdGUiIGhyZWZsYW5nPSJ2aSIgaHJlZj0iaHR0cHM6Ly93d3cuaGF0dHJpY2sub3JnL3ZpLyIgLz4NCjxsaW5rIHJlbD0iYWx0ZXJuYXRlIiBocmVmbGFuZz0idHIiIGhyZWY9Imh0dHBzOi8vd3d3LmhhdHRyaWNrLm9yZy90ci8iIC8+DQo8bGluayByZWw9ImFsdGVybmF0ZSIgaHJlZmxhbmc9Im5sLWJlIiBocmVmPSJodHRwczovL3d3dy5oYXR0cmljay5vcmcvbmwtYmUvIiAvPg0KPGxpbmsgcmVsPSJhbHRlcm5hdGUiIGhyZWZsYW5nPSJlbCIgaHJlZj0iaHR0cHM6Ly93d3cuaGF0dHJpY2sub3JnL2VsLyIgLz4NCjxsaW5rIHJlbD0iYWx0ZXJuYXRlIiBocmVmbGFuZz0iYmUiIGhyZWY9Imh0dHBzOi8vd3d3LmhhdHRyaWNrLm9yZy9iZS8iIC8+DQo8bGluayByZWw9ImFsdGVybmF0ZSIgaHJlZmxhbmc9Im1rIiBocmVmPSJodHRwczovL3d3dy5oYXR0cmljay5vcmcvbWsvIiAvPg0KPGxpbmsgcmVsPSJhbHRlcm5hdGUiIGhyZWZsYW5nPSJydSIgaHJlZj0iaHR0cHM6Ly93d3cuaGF0dHJpY2sub3JnL3J1LyIgLz4NCjxsaW5rIHJlbD0iYWx0ZXJuYXRlIiBocmVmbGFuZz0ic3IiIGhyZWY9Imh0dHBzOi8vd3d3LmhhdHRyaWNrLm9yZy9zci8iIC8+DQo8bGluayByZWw9ImFsdGVybmF0ZSIgaHJlZmxhbmc9InVrIiBocmVmPSJodHRwczovL3d3dy5oYXR0cmljay5vcmcvdWsvIiAvPg0KPGxpbmsgcmVsPSJhbHRlcm5hdGUiIGhyZWZsYW5nPSJ6aCIgaHJlZj0iaHR0cHM6Ly93d3cuaGF0dHJpY2sub3JnL3poLyIgLz4NCjxsaW5rIHJlbD0iYWx0ZXJuYXRlIiBocmVmbGFuZz0ia28iIGhyZWY9Imh0dHBzOi8vd3d3LmhhdHRyaWNrLm9yZy9rby8iIC8+DQo8bGluayByZWw9ImFsdGVybmF0ZSIgaHJlZmxhbmc9ImphIiBocmVmPSJodHRwczovL3d3dy5oYXR0cmljay5vcmcvamEvIiAvPg0KZAINDxYCHwIFbDxsaW5rIHJlbD0iYWx0ZXJuYXRlIiBtZWRpYT0iaGFuZGhlbGQsIG9ubHkgc2NyZWVuIGFuZCAobWF4LXdpZHRoOiA2NDBweCkiIGhyZWY9Imh0dHBzOi8vbS5oYXR0cmljay5vcmcvZW4iPmQCAQ8WAh4FY2xhc3MFEiBza2luLXN0YW5kYXJkIGx0chYCAgMPZBYCAgMPDxYEHghDc3NDbGFzcwUIaGF0dHJpY2seBF8hU0ICAmQWFgIBD2QWAgICD2QWAmYPZBYCAgcPZBYCAgEPZBYEZg8QZGQWAGQCAQ8QZGQWAGQCBQ9kFgJmD2QWAgIFDw8WAh4LTmF2aWdhdGVVcmwFIi9lbi9IZWxwL1ByaXZhY3kuYXNweD92aWV3PVByaXZhY3lkZAIHD2QWAmYPDxYGHwQFImJhbm5lclBhbmVsIGJhbm5lckJhY2tncm91bmRIZWFkZXIfBQICHgdWaXNpYmxlaGQWAmYPDxYEHwQFE2FkVGV4dFdyYXBwZXJIZWFkZXIfBQICZGQCCQ9kFgJmDw8WBh8EBSZiYW5uZXJQYW5lbCBiYW5uZXJCYWNrZ3JvdW5kU2lkZWJhcjE2MB8FAgIfB2hkFgJmDw8WBB8EBRRhZFRleHRXcmFwcGVyU2lkZWJhch8FAgJkZAILD2QWAmYPDxYGHwQFF2Jhbm5lclBhbmVsIGFkc0J5R29vZ2xlHwUCAh8HaGQWAmYPDxYEHwQFFGFkVGV4dFdyYXBwZXJTaWRlYmFyHwUCAmRkAg0PDxYCHwdoZGQCDw9kFgQCBw9kFgJmDw8WAh8HZ2QWAmYPFgIeC18hSXRlbUNvdW50AgoWFGYPZBYCAgEPDxYCHwIFrAE8YSBocmVmPSIvZW4vQ2x1Yi9NYXRjaGVzL01hdGNoLmFzcHg/bWF0Y2hJRD02NTY0ODE1MjUmYW1wO1NvdXJjZVN5c3RlbT1IYXR0cmljayIgdGl0bGU9Ik1BUyBEYWthci1MZXMgSW9uZiBkZSBQZW5uZWRlcGllIj5NQVMgRGFrYXImbmJzcDstJm5ic3A7TGVzIElvbmYgZGUgUGVubmVkZXBpZTwvYT4gZGQCAQ9kFgICAQ8PFgYfBAULdGlzZSBoaWRkZW4fAgWeATxhIGhyZWY9Ii9lbi9DbHViL01hdGNoZXMvTWF0Y2guYXNweD9tYXRjaElEPTY1NjQ4MTUyNCZhbXA7U291cmNlU3lzdGVtPUhhdHRyaWNrIiB0aXRsZT0iS0FDIGRlIExvdWdhLURha2FyIExpZGVycyI+S0FDIGRlIExvdWdhJm5ic3A7LSZuYnNwO0Rha2FyIExpZGVyczwvYT4gHwUCAmRkAgIPZBYCAgEPDxYGHwQFC3Rpc2UgaGlkZGVuHwIFrgE8YSBocmVmPSIvZW4vQ2x1Yi9NYXRjaGVzL01hdGNoLmFzcHg/bWF0Y2hJRD02NTY0ODE1MjMmYW1wO1NvdXJjZVN5c3RlbT1IYXR0cmljayIgdGl0bGU9IkRpYW1vbm8gRkMtQVNDIE1lbmdvbyBkZSBSdWZpc3F1ZSI+RGlhbW9ubyBGQyZuYnNwOy0mbmJzcDtBU0MgTWVuZ29vIGRlIFJ1ZmlzcXVlPC9hPiAfBQICZGQCAw9kFgICAQ8PFgYfBAULdGlzZSBoaWRkZW4fAgW2ATxhIGhyZWY9Ii9lbi9DbHViL01hdGNoZXMvTWF0Y2guYXNweD9tYXRjaElEPTY1NjQ4MTUyMiZhbXA7U291cmNlU3lzdGVtPUhhdHRyaWNrIiB0aXRsZT0iT2x5bXBpcXVlIGRlIERpYXJhZi1PU1AgUyYjMjMzO24mIzIzMztnYWwiPk9seW1waXF1ZSBkZSBEaWFyYWYmbmJzcDstJm5ic3A7T1NQIFPDqW7DqWdhbDwvYT4gHwUCAmRkAgQPZBYCAgEPDxYGHwQFC3Rpc2UgaGlkZGVuHwIFpAE8YSBocmVmPSIvZW4vQ2x1Yi9NYXRjaGVzL01hdGNoLmFzcHg/bWF0Y2hJRD02NTY0ODE0NjkmYW1wO1NvdXJjZVN5c3RlbT1IYXR0cmljayIgdGl0bGU9IkEuUy4gQ2FydG9uIFJvdWdlLWctdW5pdGNsdWIiPkEuUy4gQ2FydG9uIFJvdWdlJm5ic3A7LSZuYnNwO2ctdW5pdGNsdWI8L2E+IB8FAgJkZAIFD2QWAgIBDw8WBh8EBQt0aXNlIGhpZGRlbh8CBaoBPGEgaHJlZj0iL2VuL0NsdWIvTWF0Y2hlcy9NYXRjaC5hc3B4P21hdGNoSUQ9NjU2NDgxNDY4JmFtcDtTb3VyY2VTeXN0ZW09SGF0dHJpY2siIHRpdGxlPSJ3dSBzdHlsZS1BUklTIFRIRVNTQUxPTklLSVMgRi5DIj53dSBzdHlsZSZuYnNwOy0mbmJzcDtBUklTIFRIRVNTQUxPTklLSVMgRi5DPC9hPiAfBQICZGQCBg9kFgICAQ8PFgYfBAULdGlzZSBoaWRkZW4fAgWWATxhIGhyZWY9Ii9lbi9DbHViL01hdGNoZXMvTWF0Y2guYXNweD9tYXRjaElEPTY1NjQ4MTQ2NyZhbXA7U291cmNlU3lzdGVtPUhhdHRyaWNrIiB0aXRsZT0iRkFSIGRlIExvdWdhLXRoaWVzIGZjIj5GQVIgZGUgTG91Z2EmbmJzcDstJm5ic3A7dGhpZXMgZmM8L2E+IB8FAgJkZAIHD2QWAgIBDw8WBh8EBQt0aXNlIGhpZGRlbh8CBbABPGEgaHJlZj0iL2VuL0NsdWIvTWF0Y2hlcy9NYXRjaC5hc3B4P21hdGNoSUQ9NjU2NDgxNDY2JmFtcDtTb3VyY2VTeXN0ZW09SGF0dHJpY2siIHRpdGxlPSJGQyBMJiMyMjg7bmdlbnRhbC1BcnRodXJGcmllZGVucmVpY2giPkZDIEzDpG5nZW50YWwmbmJzcDstJm5ic3A7QXJ0aHVyRnJpZWRlbnJlaWNoPC9hPiAfBQICZGQCCA9kFgICAQ8PFgYfBAULdGlzZSBoaWRkZW4fAgWQATxhIGhyZWY9Ii9lbi9DbHViL01hdGNoZXMvTWF0Y2guYXNweD9tYXRjaElEPTY1NjQ4MTQxMyZhbXA7U291cmNlU3lzdGVtPUhhdHRyaWNrIiB0aXRsZT0iZGlhbG8gZmMtRmMgUmFzZ3VsIj5kaWFsbyBmYyZuYnNwOy0mbmJzcDtGYyBSYXNndWw8L2E+IB8FAgJkZAIJD2QWAgIBDw8WBh8EBQt0aXNlIGhpZGRlbh8CBbwBPGEgaHJlZj0iL2VuL0NsdWIvTWF0Y2hlcy9NYXRjaC5hc3B4P21hdGNoSUQ9NjU2NDgxNDEyJmFtcDtTb3VyY2VTeXN0ZW09SGF0dHJpY2siIHRpdGxlPSJUZWFtIEF1ZGkgLSBJbnRlcm5hdGlvbmFsLUNsdWIgVHJvcGljYW5hIj5UZWFtIEF1ZGkgLSBJbnRlcm5hdGlvbmFsJm5ic3A7LSZuYnNwO0NsdWIgVHJvcGljYW5hPC9hPiAfBQICZGQCCQ9kFgICAQ9kFgICBw9kFgJmD2QWAmYPEGQPFjZmAgECAgIDAgQCBQIGAgcCCAIJAgoCCwIMAg0CDgIPAhACEQISAhMCFAIVAhYCFwIYAhkCGgIbAhwCHQIeAh8CIAIhAiICIwIkAiUCJgInAigCKQIqAisCLAItAi4CLwIwAjECMgIzAjQCNRY2EAUIQWxiYW5pYW4FAjg1ZxAFDtin2YTYudix2KjZitipBQIyMmcQBQ1BesmZcmJheWNhbmNhBQMxMDBnEAUQQmFoYXNhIEluZG9uZXNpYQUCMzhnEAUIQm9zYW5za2kFAjU4ZxAFEtCR0YrQu9Cz0LDRgNGB0LrQuAUCNDNnEAUHQ2F0YWzDoAUCNjZnEAUJxIxlxaF0aW5hBQIzNWcQBQVEYW5zawUBOGcQBQdEZXV0c2NoBQEzZxAFBUVlc3RpBQIzNmcQBQxFbmdsaXNoIChVSykFATJnEAUMRW5nbGlzaCAoVVMpBQMxNTFnEAURRXNwYcOxb2wsIEVzcGHDsWEFATZnEAUZRXNwYcOxb2wsIExhdGlub2FtZXJpY2FubwUDMTAzZxAFFUVzcGHDsW9sLCBSaW9wbGF0ZW5zZQUCNTFnEAUHRXVza2FyYQUDMTEwZxAFCUZyYW7Dp2FpcwUBNWcQBQVGcnlzawUDMTA5ZxAFBkZ1cmxhbgUDMTEzZxAFBkdhbGVnbwUCNzRnEAUV4YOl4YOQ4YOg4YOX4YOj4YOa4YOYBQI5MGcQBQrXoteR16jXmdeqBQI0MGcQBQhIcnZhdHNraQUCMzlnEAUJw41zbGVuc2thBQIyNWcQBQhJdGFsaWFubwUBNGcQBQlMYXR2aWXFoXUFAjM3ZxAFD0zDq3R6ZWJ1ZXJnZXNjaAUDMTExZxAFCUxpZXR1dmnFswUCNTZnEAUGTWFneWFyBQIzM2cQBQpOZWRlcmxhbmRzBQIxMGcQBQ5Ob3JzaywgYm9rbcOlbAUBN2cQBQ5Ob3Jzaywgbnlub3JzawUDMTM2ZxAFCtmB2KfYsdiz24wFAjc1ZxAFBlBvbHNraQUCMTNnEAUKUG9ydHVndcOqcwUCMTFnEAUSUG9ydHVndcOqcywgQnJhc2lsBQI1MGcQBQhSb23Dom7EgwUCMjNnEAULU2xvdmVuxI1pbmEFAjUzZxAFDVNsb3ZlbsWhxI1pbmEFAjQ1ZxAFBVN1b21pBQE5ZxAFB1N2ZW5za2EFATFnEAUOVGnhur9uZyBWaeG7h3QFAjU1ZxAFCFTDvHJrw6dlBQIxOWcQBQZWbGFhbXMFAjY1ZxAFEM6VzrvOu863zr3Ouc66zqwFAjM0ZxAFFNCR0LXQu9Cw0YDRg9GB0LrQsNGPBQI4NGcQBRTQnNCw0LrQtdC00L7QvdGB0LrQuAUCODNnEAUO0KDRg9GB0YHQutC40LkFAjE0ZxAFDNCh0YDQv9GB0LrQuAUCMzJnEAUU0KPQutGA0LDRl9C90YHRjNC60LAFAjU3ZxAFEuS4reaWh++8iOeugOS9k++8iQUCMTVnEAUJ7ZWc6rWt7Ja0BQIxN2cQBQnml6XmnKzoqp4FAjEyZ2RkAhcPZBYGAgMPZBYEAgEPZBYCAgEPZBYEAgIPZBYCZg8WAh8HZ2QCAw9kFgJmDxYCHwdnZAIDD2QWAgIBDw8WAh4HSGVhZGluZwUTQWxsLVRpbWUgU3RhdGlzdGljc2QWGAIBDxYCHwIFAjIyZAIDDxYCHwIFBVllYXJzZAIFDxYCHwIFAjU0ZAIHDxYCHwIFCUxhbmd1YWdlc2QCCQ8WAh8CBQMxMzVkAgsPFgIfAgUJQ291bnRyaWVzZAINDxYCHwIFDDEzwqA2MjTCoDE3N2QCDw8WAh8CBQtUb3RhbCB1c2Vyc2QCEQ8WAh8CBQ0zNDnCoDg5MMKgOTI1ZAITDxYCHwIFC0ZvcnVtIHBvc3RzZAIVDxYCHwIFDTc1OcKgOTI0wqAwMjBkAhcPFgIfAgUOTWF0Y2hlcyBwbGF5ZWRkAgcPZBYCZg9kFgJmDxYCHwgCBBYKZg9kFgICAQ8WAh8CZGQCAQ9kFgQCAQ8PFgQfBgUnfi9JbWcvV2VsY29tZUJhY2sveW91cmV0aGVib3NzX2Z1bGwucG5nHgdUb29sVGlwBRlNYW5hZ2UgLSBhdCB5b3VyIG93biBwYWNlFgIeA3JlbAUSbGlnaHRib3hbcm9hZHRyaXBdFgJmDw8WBB4ISW1hZ2VVcmwFKH4vSW1nL1dlbGNvbWVCYWNrL3lvdXJldGhlYm9zc19zbWFsbC5wbmceDUFsdGVybmF0ZVRleHQFL09ubGluZSBmb290YmFsbCBtYW5hZ2VyIGdhbWUgLSBNYXRjaCBvcmRlciB2aWV3ZGQCAw8WAh8CBfcBPGgzPk1hbmFnZSAtIGF0IHlvdXIgb3duIHBhY2U8L2gzPjxwPkhhdHRyaWNrIGlzIGEgZm9vdGJhbGwgc3RyYXRlZ3kgZ2FtZSB3aGVyZSB5b3UgYnVpbGQgYW5kIG1hbmFnZSB5b3VyIHRlYW0gZm9yIHRoZSBsb25nIHRlcm0uIExvZyBpbiBldmVyeSBkYXkgb3IganVzdCBvbmNlIGEgd2VlayAtIGlmIHlvdSBtYWtlIHRoZSByaWdodHMgY2FsbHMgeW91J2xsIGhhdmUgdGhlIHNhbWUgY2hhbmNlIHRvIGJlIGEgY2hhbXBpb24hPC9wPmQCAw9kFgQCAQ8PFgQfBgUkfi9JbWcvV2VsY29tZUJhY2svYnVpbGR0ZWFtX2Z1bGwucG5nHwoFGUJ1aWxkIGFuZCB0cmFpbiB5b3VyIHRlYW0WAh8LBRJsaWdodGJveFtyb2FkdHJpcF0WAmYPDxYEHwwFJX4vSW1nL1dlbGNvbWVCYWNrL2J1aWxkdGVhbV9zbWFsbC5wbmcfDQUqT25saW5lIGZvb3RiYWxsIG1hbmFnZXIgZ2FtZSAtIFBsYXllciB2aWV3ZGQCAw8WAh8CBeIBPGgzPkJ1aWxkIGFuZCB0cmFpbiB5b3VyIHRlYW08L2gzPjxwPkRldmVsb3AgeW91ciB0ZWFtIHRocm91Z2ggdHJhaW5pbmcuIE1hbmFnZSB5b3VyIGZpbmFuY2VzLiBGaW5kIG5ldyBwbGF5ZXJzIG9uIHRoZSB0cmFuc2ZlciBtYXJrZXQgb3Igc3RhcnQgeW91ciBvd24geW91dGggdGVhbSB0byBmb3N0ZXIgeW91ciBvd24gdGFsZW50cyBmb3IgdGhlIG5leHQgZ29sZGVuIGdlbmVyYXRpb24uPC9wPmQCBQ9kFgQCAQ8PFgQfBgUqfi9JbWcvV2VsY29tZUJhY2svYmF0dGxlZm9ydHJvcGh5X2Z1bGwucG5nHwoFF091dHNtYXJ0IHlvdXIgb3Bwb25lbnRzFgIfCwUSbGlnaHRib3hbcm9hZHRyaXBdFgJmDw8WBB8MBSt+L0ltZy9XZWxjb21lQmFjay9iYXR0bGVmb3J0cm9waHlfc21hbGwucG5nHw0FHE9ubGluZSBmb290YmFsbCBtYW5hZ2VyIGdhbWVkZAIDDxYCHwIF9QE8aDM+T3V0c21hcnQgeW91ciBvcHBvbmVudHM8L2gzPjxwPllvdSBjb21wZXRlIGFnYWluc3QgaHVtYW4gbWFuYWdlcnMgaW4gbmF0aW9uYWwgbGVhZ3VlcyBhbmQgY3Vwcy4gU3RhcnQgaW4gdGhlIGxvd2VyIGRpdmlzaW9ucyAtIHRoZW4gY2xpbWIgeW91ciB3YXkgdG8gdGhlIHRvcCEgWW91IGNhbiBhbHNvIGNyZWF0ZSB5b3VyIHByaXZhdGUgdG91cm5hbWVudHMgdG8gcGxheSB3aXRoIGZyaWVuZHMuPGJyIC8+PGJyIC8+PC9wPmQCBw9kFgQCAQ8PFgQfBgUrfi9JbWcvV2VsY29tZUJhY2svY29tbXVuaXR5YW5kYXBwc19mdWxsLnBuZx8KBRJDb21tdW5pdHkgYW5kIGFwcHMWAh8LBRJsaWdodGJveFtyb2FkdHJpcF0WAmYPDxYEHwwFLH4vSW1nL1dlbGNvbWVCYWNrL2NvbW11bml0eWFuZGFwcHNfc21hbGwucG5nHw0FHE9ubGluZSBmb290YmFsbCBtYW5hZ2VyIGdhbWVkZAIDDxYCHwIF7AE8aDM+Q29tbXVuaXR5IGFuZCBhcHBzPC9oMz48cD5UaGUgY29tbXVuaXR5IHJlYWxseSBzdGFuZHMgb3V0IGluIEhhdHRyaWNrISBKb2luIG91ciBmb3J1bXMgYW5kIG1ha2UgbmV3IGZyaWVuZHMgZnJvbSBhbGwgb3ZlciB0aGUgd29ybGQuIFdlIGhhdmUgZ3JlYXQgYXBwcyBmb3IgaU9TIGFuZCBBbmRyb2lkLCBhcyB3ZWxsIGFzIGEgcmFuZ2Ugb2YgdGhpcmQtcGFydHkgc29mdHdhcmUgdG8gZG93bmxvYWQuPC9wPmQCCQ9kFh5mDxYCHwIFkQRIYXR0cmljayBpcyBhbiBvbmxpbmUgZm9vdGJhbGwgbWFuYWdlciBnYW1lIHdoZXJlIHlvdSB0YWtlIHRoZSByb2xlIG9mIGEgbWFuYWdlciBvbiBhIG1pc3Npb24gdG8gdGFrZSB5b3VyIGNsdWIgdG8gdGhlIHRvcCBvZiB0aGUgbGVhZ3VlIHN5c3RlbSEgWW91IGFyZSBpbiBjaGFyZ2Ugb2YgYWxsIGFzcGVjdHMgb2YgY2x1YiBtYW5hZ2VtZW50OiBCdXlpbmcgYW5kIHNlbGxpbmcgcGxheWVycyBvbiB0aGUgdHJhbnNmZXIgbWFya2V0LCBkZWNpZGluZyB3aGF0IHNraWxscyB0byB0cmFpbiBvbiB0aGUgcHJhY3RpY2UgZmllbGQsIHByZXBhcmluZyBhIHRhY3RpY2FsIHBsYW4gZm9yIGVhY2ggbWF0Y2ggeW91ciB0ZWFtIHdpbGwgcGxheSBpbiB5b3VyIG5hdGlvbmFsIGxlYWd1ZSBhbmQgY3VwLCBzdWNoIGFzIDxhIGhyZWY9Ii9lbi9Xb3JsZC9MZWFndWVzL0xlYWd1ZS5hc3B4P0xlYWd1ZUlEPTIiPkVuZ2xhbmQ8L2E+IGFuZCA8YSBocmVmPSIvZW4vV29ybGQvQ3VwL0N1cC5hc3B4P0N1cElEPTMiPkVuZ2xpc2ggQ3VwPC9hPi4gZAIBDxYCHwIF+QFXaGVuIHlvdXIgbWF0Y2gga2lja3Mgb2ZmLCB5b3VyIG1hdGNoIHdpbGwgYmUgc2ltdWxhdGVkIGJ5IG91ciBzeXN0ZW0gYW5kIHlvdSBjYW4gZm9sbG93IHRoZSBhY3Rpb24gaW4gb3VyIGxpdmUgY29tbWVudGFyeSB2aWV3ZXIsIGFuZCBtZWFud2hpbGUgY2hhdCB3aXRoIHlvdXIgb3Bwb3NpbmcgbWFuYWdlciEgSWYgeW91IHByZWZlciwgeW91IGNhbiB3YXRjaCBhbmQgYW5hbHlzZSB0aGUgbWF0Y2ggYWZ0ZXJ3YXJkcyBpbnN0ZWFkLiBkAgIPFgIfAgXHAkhhdHRyaWNrIGlzIGFib3ZlIGFsbCBhIHN0cmF0ZWdpYyBmb290YmFsbCBtYW5hZ2VtZW50IGdhbWUgd2hlcmUgeW91IGhhdmUgdG8gcGxhbiBmb3IgdGhlIGxvbmcgdGVybS4gU2hvdWxkIHlvdSBpbnZlc3QgaW4gYmV0dGVyIHlvdXRoIGZhY2lsaXRpZXMgb3Igc3BlbmQgdGhlIG1vbmV5IHRvIGJ1eSBhbiBhZ2Vpbmcgc3RhciBwbGF5ZXIgdGhhdCBjYW4gaW5jcmVhc2UgeW91ciB0ZWFtIHBlcmZvcm1hbmNlIGluIHRoZSBzaG9ydCB0ZXJtPyBTaG91bGQgeW91IHByb21vdGUgdGFsZW50ZWQgZGVmZW5kZXJzIG9yIGF0dGFja2VycyBpbiB5b3VyIHlvdXRoIGFjYWRlbXk/IGQCAw8WAh8CBbsBQ2hvb3NlIHdlbGwsIHlvdXIgdGVlbmFnZSB0YWxlbnRzIG1heSB3ZWxsIGJlIHRoZSBzdGFycyBvZiB0aGUgdGVhbXMgbWFueSBzZWFzb25zIGZyb20gbm93LCBtYXliZSBldmVuIHRoZSBuZXh0IExpb25lbCBNZXNzaSwgQ3Jpc3RpYW5vIFJvbmFsZG8gb3IgS3lsaWFuIE1iYXBww6kgb2YgdGhlIEhhdHRyaWNrIHVuaXZlcnNlIWQCBA8WAh8CBawCQSBiaWcgcGFydCBvZiB0aGUgZXhjaXRlbWVudCBpcyB0aGF0IGl0IGlzIGEgbXVsdGlwbGF5ZXIgZXhwZXJpZW5jZSAtIHRoZSB0ZWFtcyB5b3UgZmFjZSBhcmUgbWFuYWdlZCBieSBvdGhlciBodW1hbnMsIHdobyB3aWxsIHRyeSB0byBvdXRzbWFydCB5b3UuIFRoZXJlIGlzIGEgcmljaCBjb21tdW5pdHkgdGhhdCB5b3UgY2FuIGRpdmUgaW50byB0byBsZWFybiBhbGwgYWJvdXQgdGhlIGJlc3Qgd2F5cyB0byB0cmFpbiwgc2V0IHVwIHlvdXIgdGVhbSB0YWN0aWNzIGFuZCBpbXByb3ZlIHlvdXIgY2x1YiBmaW5hbmNpYWxseS4gZAIFDxYCHwIF5QRZb3VyIHN0YXIgcGxheWVycyBjYW4gZXZlbiBiZSBwaWNrZWQgZm9yIGludGVybmF0aW9uYWwgZHV0eSwgcGxheWluZyBmb3IgdGhlIDxhIGhyZWY9Ii9lbi9DbHViL05hdGlvbmFsVGVhbS9OYXRpb25hbFRlYW0uYXNweD90ZWFtSWQ9MzAwMSIgdGl0bGU9IkVuZ2xhbmQiPkVuZ2xhbmQ8L2E+IG5hdGlvbmFsIHRlYW0hIEV2ZXJ5IHllYXIsIEhhdHRyaWNrIG9yZ2FuaXNlcyBhIFdvcmxkIEN1cCwgZWl0aGVyIGZvciBzZW5pb3IgdGVhbXMgb3IgdGhlIFUyMCBzcXVhZHMuIFRoZSBjdXJyZW50IGNoYW1waW9ucyBvZiB0aGUgSGF0dHJpY2sgV29ybGQgQ3VwIGFyZSA8YSBocmVmPSIvZW4vQ2x1Yi9OYXRpb25hbFRlYW0vTmF0aW9uYWxUZWFtLmFzcHg/dGVhbUlkPTMwMzkiIHRpdGxlPSImIzIxNDtzdGVycmVpY2giPsOWc3RlcnJlaWNoPC9hPiwgY2hlY2sgb3V0IHRoZSBXb3JsZCBDdXAgZmluYWwgbWF0Y2ggaGVyZSEgPGEgaHJlZj0iL2VuL0NsdWIvTWF0Y2hlcy9NYXRjaC5hc3B4P21hdGNoSUQ9NjUzNTkyNzM4JmFtcDtTb3VyY2VTeXN0ZW09SGF0dHJpY2siIHRpdGxlPSImIzIxNDtzdGVycmVpY2gtSXNyYWVsIj7DlnN0ZXJyZWljaCZuYnNwOy0mbmJzcDtJc3JhZWw8L2E+ZAIGDxYCHwIFsQJJZiB5b3UgYmVjb21lIGEgZ3JlYXQgbWFuYWdlciB5b3Vyc2VsZiwgeW91IGNhbiBzdGFuZCBpbiB0aGUgZWxlY3Rpb25zIHRvIHJ1biB0aGUgbmF0aW9uYWwgdGVhbSBhbmQgYmUgZWxlY3RlZCBpbnRvIHRoZSBvZmZpY2UgYnkgeW91ciBmZWxsb3cgb25saW5lIG1hbmFnZXJzLiBBdCB0aGUgbW9tZW50LCB0aGVyZSBhcmUgMTM2IG5hdGlvbmFsIGxlYWd1ZXMgaW4gSGF0dHJpY2ssIGFuZCB5b3UgY2FuIGJlIGEgY2FuZGlkYXRlIGZvciBhbnkgb2YgdGhlbSwgZXZlbiBpZiB5b3VyIG93biB0ZWFtIGlzIGluIGFub3RoZXIgbGVhZ3VlLmQCBw8WAh8CBc4BSW4gSGF0dHJpY2ssIHRoZXJlIGlzIGFsd2F5cyBzb21ldGhpbmcgdG8gZG8sIHdoZXRoZXIgaXQgaXMgdG8gaGFuZyBvdXQgaW4gdGhlIGZvcnVtcyB0byB0YWxrIGFib3V0IEhhdHRyaWNrIG9yIGdlbmVyYWwgZm9vdGJhbGwgbmV3cywgb3IgdG8gdHJ5IHRvIGZpbmQgYmFyZ2FpbnMgb24gdGhlIHRyYW5zZmVyIG1hcmtldCBkdXJpbmcgc2lsbHkgc2Vhc29uLiBkAggPFgIfAgW1AkJ1dCBpdCBpcyBpbXBvcnRhbnQgdG8ga25vdyB0aGF0IEhhdHRyaWNrIGlzIGFsc28gYSBnYW1lIHRoYXQgeW91IGNhbiBhbHdheXMgcGxheSBhdCB5b3VyIG93biBwYWNlLiBJZiB5b3Ugc3BlbmQgMzAgbWludXRlcyBhIHdlZWsgdG8gc2V0IHlvdXIgbWF0Y2ggb3JkZXJzIGFuZCB1cGRhdGUgdGhlIHRyYWluaW5nIHBsYW5zIG9mIHlvdXIgdGVhbSwgeW91IHdpbGwgYmUgYWJsZSB0byBjb21wZXRlIGFuZCBwZXJmb3JtIHdlbGwgaW4gdGhlIG1haW4gY29tcGV0aXRpb25zIC0gYXMgbG9uZyBhcyB5b3UgbWFrZSBzbWFydCBkZWNpc2lvbnMuIGQCCQ8WAh8CBYEDVW5saWtlIG1hbnkgb3RoZXIgZ2FtZXMsIHlvdSBkb27igJl0IG5lZWQgdG8gbG9nIGluIGV2ZXJ5IGRheSB0byBjb2xsZWN0IGJvbnVzZXMgb3IgZ2FpbiBpbi1nYW1lIGN1cnJlbmN5LiBUaGVyZSBpcyBubyB3YXkgdG8gYnV5IGluLWdhbWUgYWR2YW50YWdlcyBpbiBIYXR0cmljay4gWW91IGNhbiBpbnN0ZWFkIGJlY29tZSBhIDxhIGhyZWY9Ii9lbi9IZWxwL1N1cHBvcnRlci9BYm91dC5hc3B4Ij5IYXR0cmljayBTdXBwb3J0ZXI8L2E+LCB3aGljaCBnaXZlcyB5b3UgYSBsb3Qgb2YgZmVhdHVyZXMgZGVzaWduZWQgdG8gbWFrZSB0aGUgZ2FtZSBtb3JlIGZ1biBhbmQgaW50ZXJlc3RpbmcsIGJ1dCB3aGljaCBpbmNsdWRlcyBubyBhY3R1YWwgaW4tZ2FtZSBhZHZhbnRhZ2VzLmQCCg8WAh8CBYECSGF0dHJpY2sgaXMgdGhlIG9yaWdpbmFsIG9ubGluZSBmb290YmFsbCBtYW5hZ2VyIGdhbWUsIGFuZCB3ZSBoYXZlIGJlZW4gPGEgaHJlZj0iaHR0cHM6Ly93d3cud2lraXBlZGlhLm9yZy93aWtpL0hhdHRyaWNrXyh2aWRlb19nYW1lKSI+b25saW5lIHNpbmNlIDE5OTc8L2E+LiBUaGUgZm91bmRlcnMgYXJlIHN0aWxsIGFjdGl2ZSBhbmQgYXJlIHN0aWxsIGNvbW1pdHRlZCB0byBvZmZlcmluZyBIYXR0cmljayBhcyBhIGZyZWUgZm9vdGJhbGwgZ2FtZS5kAgsPFgIfAgX6AVdlIGZlZWwgdGhhdCBIYXR0cmljayBicmluZ3MgdG9nZXRoZXIgdGhlIGJlc3QgZnJvbSB0aGUgdHJhZGl0aW9uYWwgY29tcHV0ZXItYmFzZWQgPGEgaHJlZj0iL2VuL3NvY2Nlci1tYW5hZ2VyLWdhbWUuYXNweCI+c29jY2VyIG1hbmFnZXIgZ2FtZTwvYT4sIHN1Y2ggYXMgdGhlIEZvb3RiYWxsIE1hbmFnZXIgc2VyaWVzLCBidXQgaW4gYSBtb3JlIGV4Y2l0aW5nIHdheSBhcyB5b3UgYWx3YXlzIHBsYXkgYWdhaW5zdCByZWFsIHBlb3BsZS5kAgwPFgIfAgXnAUl0IGFsc28gaW5jbHVkZXMgYXNwZWN0cyBvZiBmYW50YXN5IGZvb3RiYWxsIGdhbWVzIGFuZCBmcm9tIGNvbnNvbGUgZm9vdGJhbGwgZ2FtZXMgc3VjaCBhcyBGSUZBIFVsdGltYXRlIFRlYW0sIHdoZXJlIHlvdSBjb2xsZWN0IGFuZCBidWlsZCBmb290YmFsbCBzcXVhZHMgZWl0aGVyIHRvIHBsYXkgYWdhaW5zdCBvdGhlciB1c2VycyBvciB0byBjb2xsZWN0IHRyb3BoaWVzIGFuZCBhY2hpZXZlbWVudHMuIGQCDQ8WAh8CBcYDV2UgYmlkIHlvdSBhbGwgdmVyeSB3ZWxjb21lIHRvIEhhdHRyaWNrIC0gdGhlIGJlc3QgZnJlZSBmb290YmFsbCBtYW5hZ2VyIGdhbWUgb3V0IHRoZXJlISBJdCBpcyB0b3RhbGx5IGZyZWUgdG8gc2lnbiB1cCwgbm8gZG93bmxvYWRzIGFyZSByZXF1aXJlZCBhbmQgeW91IGFsc28gaGF2ZSBhY2Nlc3MgdG8gYW1hemluZyBmcmVlIGFwcHMgZm9yIDxhIGhyZWY9Imh0dHA6Ly9pdHVuZXMuYXBwbGUuY29tL2FwcC9oYXR0cmljay9pZDQ4MzU2OTcxNCI+aU9TPC9hPiBvciA8YSBocmVmPSJodHRwczovL3BsYXkuZ29vZ2xlLmNvbS9zdG9yZS9hcHBzL2RldGFpbHM/aWQ9b3JnLmhhdHRyaWNrLmhhdHRyaWNrIj5BbmRyb2lkPC9hPiB0aHJvdWdoIHdoaWNoIHlvdSBjYW4gbWFuYWdlIGFsbCBhc3BlY3RzIG9mIHRoZSBnYW1lLCBtYWtpbmcgSGF0dHJpY2sgYWxzbyBhIG1vYmlsZSBmb290YmFsbCBnYW1lLmQCDg8WAh8CBXdCdXQgYmV3YXJlLCBIYXR0cmljayBjYW4gYmUgYWRkaWN0aXZlIC0gbWFueSBvZiBvdXIgdXNlcnMgaGF2ZSBwbGF5ZWQgZm9yIDEwIHllYXJzIG9yIG1vcmUgYW5kIGFyZSBzdGlsbCBnb2luZyBzdHJvbmcuIGQCGQ8PFgIfB2hkZAIdD2QWAmYPDxYGHwQFImJhbm5lclBhbmVsIGJhbm5lckJhY2tncm91bmRGb290ZXIfBQICHwdoZBYCZg8PFgQfBAUTYWRUZXh0V3JhcHBlckZvb3Rlch8FAgJkZAIrD2QWAgIBD2QWBgIDD2QWBgIBDxBkZBYAZAIDDxBkZBYAZAIHDxBkZBYAZAIFD2QWAgIBDxBkZBYAZAIHD2QWAgICD2QWAgIBDxBkZBYAZGRw5OdsP7ivlxV1GVIqeXJws5nGfg==",
        "__VIEWSTATEGENERATOR": "98A44CFC",
        EVENT_VALIDATION_KEY: "/wEdADz0XfECtiFlPyIfLBnk/8zriglqPO6+DdaB3bitcxQLuVoCRKwgaeTtmnUdF2Q+ccVLB0ONocJ0i+gYcXxIhIq4e15NCeIC1fJJ3nxW10Xv6dMePt3XGy3xASslciR8Z9tDgecpx1acBv/ZR7Ws0IqKCNYfwnjZgJM1tacKPHdl6+MkGJ5tPf+j/lCmiWD5oTeEZm/rd4lTaVRBwTPnfsWEBOpiyBMbhtGx+gc6xdgpN5Kp0VGsCB5l1XGJ7hhvXnObZPKY2eDdoUZgfcJZZOOcNLtPUvy58iC1f+vEEyycMiR85BVrCpXtZR27YKsU8ZaVUj2CQUNkDx3giEayPEDduy3AAegdS3C2XP/yqs/GVjuaJ23wqVgs16MtSOAXeN+1Wp9oPAvPJBjtezLAquuzMCAytvXJobQ3kkd5I5tsmMSKgX55BssM6BKjlz6d15YdK3Xcbv6D93KSTl3q7osv1CUg4d4ryWccMrz6PXXlYoKqBK3Bj2zDV29HaEiz1ClvGw9PbnAD9YIgG2zk/GQqd+kdOdaq/Ej6IJ4o5fONCjcXe9KEUcfC+Q3C4s51nU7AwyeKFeNGciLWGrhqHlEPqIH2O3XvkToQTXxuQkucJOUBYnpoK5SaRzW1WoEsoFPQ94QJLcZ7NZrWvYMzEKutzsLuvnnjSW3XgHo31ZcTSzSrgjQ10zPou9/vYCaj9leaUs111r9vkf77BFjhRQ7BoslG3Ponl2YwFqbh1o2UApZlbuuHXcqRHEBL2hV0dn33esswVzZIYHTlXwTMtx+cMbFDtxx6lHaqtqdUNHgqwfR0ICr55vOanM0273BM6y1/k8AYe6LcBNpT+uhM9BYJ+TE93QctsRSlGmmzXXlp7i8Y2CylLMVSNayZpV/meI4uYR2LanKt7XAXN1H9doKA2Zh2ftJUjKn1IXCqd39P8EJY3qQB0IsGtFAFdmveeKx32XKWJPEEzv9pjGRsqO3eIPxq69dwCBiarszIGvJdWLUezuCxi7rJVOh2mQELUKjObNzLBQWWewa+DtrggcHbNBPPhoRZPnoMrnMgcCsxeBUk3+F2cBblr2G9CS2IlAaMKIVBT72CRUsQeTGlyJSVLknOtVNEAN+DSMHN0NurwGbnZpbl9SUOufN5nAYvYtu9dfrCMb5c8fPBjlqoc+NBx4i5WRxjOcbKbiOwPKIIkjH6rovQFTOivcjWwnGmOeDg+AdTdWo+hmnF+WfQ10NVVtcJ8XeRtgrb9jBtNLVgxmiQ/81RVGqGQ2F/Hb19qVCLmnRVqGPNLkT8DHuci8Pclu3V6g==",
        "ctl00$CPHeader$ucMenu$ucLanguages$ddlLanguages": "2",
        "loginname": "{{signup.loginname}}",
        "password": "{{signup.password}}",
        "ctl00$CPContent$ucLogin$txtUserName": "stevensson",
    }

    LOAD_MORE_TRANSFERS_FORM = {
        "ctl00_ctl00_sm_HiddenField": TOKEN,
        "__EVENTTARGET": "ctl00$ctl00$CPContent$CPMain$lnkMoreTransfers",
    }

    PASSWORD_FIELD = "ctl00$CPContent$ucLogin$txtPassword"

    LOGOUT_LINK = "?action=logout"

    PLAYERS_LINK = "Club/Players"
    TRANSFER_COMPARE_LINK = "Club/Transfers/TransferCompare"
    TEAM_LINK_PATTERN = r"Club/\?TeamID="
    TEAM_FINANCE_LINK = "Club/Finances/?teamId="

    FURTHER_TRANSFERS_LINK_ID = "ctl00_ctl00_CPContent_CPMain_lnkMoreTransfers"

    # TODO properly support English too
    DICTIONARY = {
        "age": LanguageDependentText(hungarian=r"(?P<years>\d+) éves és (?P<days>\d+) napos",
                                     english=None,
                                    ),
        "nt": LanguageDependentText(hungarian="válogatott csapatának is tagja!",
                                    english=None,
                                   ),
        "nt_prospect": LanguageDependentText(hungarian="nemzeti csapatának jelöltje",
                                             english=None,
                                            ),
        "app_error": LanguageDependentText(hungarian="Alkalmazáshiba",
                                           english=None,
                                          ),
        "avg_price_block": LanguageDependentText(hungarian=">Átlagérték<",
                                                 english=None,
                                                ),
        "total": LanguageDependentText(hungarian="Összesen:",
                                       english=None,
                                      ),
        "board_reserves": LanguageDependentText(hungarian="Az igazgatóság tartaléka:",
                                                english=None,
                                               )
    }

    def __init__(self, currency="eFt"):
        """Initialise a new session before login"""
        self.currency = currency
        self.session = None
        self.server_url = None
        self.server_id = None
        self.team = None
        self.language = None
        self.logged_in = False

    def _parse_team_id(self, page):
        """Parse and return the team id or raise a RuntimeError"""
        if match := re.search(r"currentTeamId=(?P<team_id>\d+)",
                              page.request.headers["Cookie"]):
            team_id = int(match.group("team_id"))
        else:
            raise RuntimeError("Unexpected Cookie: '{}'"
                               .format(page.request.headers["Cookie"]))
        return team_id

    def _parse_team_name_by_id(self, page, team_id):
        """Parse and return the team's name or raise a RuntimeError"""
        regex = (r'a href="/{}{}" title="(?P<name>[^"]+)"'
                 .format(self.TEAM_LINK_PATTERN, team_id))
        if match := re.search(regex, page.text):
            name = match.group("name")
        else:
            self._raise_and_try_dumping_page_error(
                "Failed to find the team's name!",
                "team_name", page, regex,
            )

        return name

    def _parse_page_language(self, page):
        """Parse and return the page's language or raise a RuntimeError"""
        page_language_regex = r'lang="(?P<language_id>[^"]+)"'
        if match := re.search(page_language_regex, page.text):
            page_language_pattern_to_script_language_mapping = {
                "hu": LanguageDependentText.SUPPORTED_LANGUAGES[0],
                "en": LanguageDependentText.SUPPORTED_LANGUAGES[1],
            }
            language_id = match.group("language_id")
            if language_id not in page_language_pattern_to_script_language_mapping:
                supported_language_ids = " ".join(page_language_pattern_to_script_language_mapping.keys())
                raise RuntimeError(("Failed to detect the page's language from '{}'"
                                    " The supported language codes are '{}'")
                                   .format(language_id, supported_language_ids))

            language = page_language_pattern_to_script_language_mapping[language_id]
        else:
            self._raise_and_try_dumping_page_error(
                "Failed to detect the page's language", "lang", page,
                page_language_regex,
            )
        return language

    def _open_link(self, link, use_server_url=True, use_headers=True, method="get", data=None):
        """Open the link using the live session and return the HTML response
        Raise an exception if the final response code isn't 200 (OK).
        If `method` is not a valid session method, AttributeError will be raised
        """
        session_method = getattr(self.session, method)

        url = "{}/{}".format(self.server_url, link) if use_server_url else link

        params = {}
        if use_headers:
            params["headers"] = self.HEADER
        if data is not None:
            params["data"] = data

        response = session_method(url, **params)
        response.raise_for_status()

        if self.logged_in:
            app_error_key = "app_error"
            app_error_pattern = self.DICTIONARY[app_error_key].translate_to(self.language)
            if re.search(app_error_pattern, response.text):
                if data is not None:
                    pprint("We've tried to use this data:{}".format(data))
                self._raise_and_try_dumping_page_error(
                    "'{}'!".format(app_error_pattern), app_error_key, response
                )

        return response

    def __enter__(self):
        """Login to Hattrick
        If any step fail, an exception is raised so if we managed to enter, we are in.
        In case of an exception, __exit__ will run, so don't worry.
        """
        try:
            self.session = requests.Session()

            self._open_link(self.MAIN_PAGE, use_server_url=False, use_headers=False)

            self.LOGIN_FORM[self.PASSWORD_FIELD] = getpass()

            response = self._open_link(self.LOGIN_PAGE, use_server_url=False, method="post",
                                       data=self.LOGIN_FORM)
            response.raise_for_status()
            if match := re.search(r"^(?P<server_url>.*www(?P<server_id>\d+)\.hattrick\.org)",
                                  response.url):
                self.server_url = match.group("server_url")
                self.server_id = int(match.group("server_id"))
                team_id = self._parse_team_id(response)
                team_name = self._parse_team_name_by_id(response, team_id)
                self.team = Team(team_id=team_id, name=team_name)
                self.language = self._parse_page_language(response)
                print("We're in! :)")
                self.logged_in = True
            else:
                raise RuntimeError("Unexpected URL: '{}'".format(response.url))
        except Exception:
            self.__exit__(*sys.exc_info())
            raise

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Logout and exit the session too, if we were logged in and/or the session was live"""
        if self.logged_in:
            self._open_link(self.LOGOUT_LINK)
            self.logged_in = False
            print("We're out! :)")

        if self.session is not None:
            self.session.__exit__()

    def download_player_list_page(self):
        """Return the player list page html response object"""
        players_url_suffix = "{}/?TeamID={}".format(self.PLAYERS_LINK, self.team.id)
        return self._open_link(players_url_suffix)

    def _parse_player_age(self, player_page):
        """Parse and return the player's age or raise a RuntimeError"""
        age_pattern = self.DICTIONARY["age"].translate_to(self.language)
        if match := re.search(age_pattern, player_page.text):
            age = Age(int(match.group("years")), int(match.group("days")))
        else:
            self._raise_and_try_dumping_page_error(
                "Failed to find the player's age", "age", player_page, age_pattern
            )
        return age

    def _parse_player_tsi(self, player_page):
        """Parse and return the player's TSI or raise a RuntimeError"""
        tsi_on_next_line_pattern = r"TSI</td>"
        tsi_value_pattern = r">(?P<value>[^><]+)</td>"

        tsi = FindState()
        for byte_line in player_page.iter_lines():
            string_line = _bytes_to_string(byte_line)

            _find_after_a_start_match(tsi_on_next_line_pattern, tsi_value_pattern,
                                      string_line, tsi)
            if tsi.found():
                break

        return tsi.get_int_or_raise_and_try_dumping_page_error(
            "Failed to find the player's tsi", "tsi", player_page, tsi_value_pattern
        )

    def _parse_national_team_player_status(self, player_page):
        """Parse and return the player's ::NationalPlayerStatus"""
        nt_pattern = self.DICTIONARY["nt"].translate_to(self.language)
        if match := re.search(nt_pattern, player_page.text):
            nt_player = True
        else:
            nt_player = False

        nt_prospect_pattern = self.DICTIONARY["nt_prospect"].translate_to(self.language)
        if match := re.search(nt_prospect_pattern, player_page.text):
            nt_player_prospect = True
        else:
            nt_player_prospect = False

        return NationalPlayerStatus(is_national_team_player=nt_player,
                                    is_national_team_player_prospect=nt_player_prospect,
                                   )

    def _find_value_on_page_for_key(self, page, key):
        """Find and return the current value of `key` on the page or raise a RuntimeError"""
        regex = r'{}.*value="(?P<value>[^"]+)"'.format(key)
        if match := re.search(regex, page.text):
            value = match.group("value")
        else:
            self._raise_and_try_dumping_page_error(
                "Failed to find the value of '{}'".format(key), "value",
                page, regex
            )
        return value

    def _update_form_with_dynamic_value(self, page, key, form):
        """Find the `value` for the `key` on the `page` and update the `form` with it at `key`"""
        value = self._find_value_on_page_for_key(page, key)
        form[key] = value

    def _load_more_transfers(self, page, link):
        """Load more transfers using the original `page` and return this "updated page"
        which supposed to list more transfers
        """
        for key in (self.EVENT_VALIDATION_KEY, self.VIEW_STATE_KEY, self.VIEW_STATE_GENERATOR_KEY):
            self._update_form_with_dynamic_value(
                page, key, self.LOAD_MORE_TRANSFERS_FORM
            )
        return self._open_link(link, method="post", data=self.LOAD_MORE_TRANSFERS_FORM)

    def _download_sell_price_etimation_page(self, player_page):
        """Return the requested page's html response object"""
        regex = r'a href="/(?P<link>{}[^"]+)"'.format(self.TRANSFER_COMPARE_LINK)
        if match := re.search(regex, player_page.text):
            link = match.group("link")
            price_estimation_page = self._open_link(link)

            there_is_more_transfer_to_load = re.search(self.FURTHER_TRANSFERS_LINK_ID,
                                                       price_estimation_page.text)
            if there_is_more_transfer_to_load:
                price_estimation_page = self._load_more_transfers(price_estimation_page, link)
        else:
            self._raise_and_try_dumping_page_error(
                "Failed to find the player's transfer compare link", "tcl",
                player_page, regex
            )
        return price_estimation_page

    def _parse_player_sell_base_price(self, player_page):
        """Parse and return the player's base sell price
        To do that we need to navigate to the sell price estimation page first
        """
        price_estimation_page = self._download_sell_price_etimation_page(player_page)

        avg_price_block_pattern = self.DICTIONARY["avg_price_block"].translate_to(self.language)
        price_pattern = r'right transfer-compare-bid">(?P<value>[0-9 ]+) {}</th>'.format(self.currency)

        sell_base_price = FindState()
        for byte_line in price_estimation_page.iter_lines():
            string_line = _bytes_to_string(byte_line)

            _find_after_a_start_match(avg_price_block_pattern, price_pattern,
                                      string_line, sell_base_price)
            if sell_base_price.found():
                break

        return sell_base_price.get_int_or_raise_and_try_dumping_page_error(
            "Failed to find the player's base sell price", "bsp", price_estimation_page,
            price_pattern
        )

    def _download_player_info_into(self, player):
        """Download all the info we need into the specified `player`"""
        response = self._open_link(player.link)
        player.age = self._parse_player_age(response)
        player.tsi = self._parse_player_tsi(response)
        player.ntp_status = self._parse_national_team_player_status(response)
        player.sell_base_price = self._parse_player_sell_base_price(response)

    def download_player_by_name(self, name, players_list_page,
                                raise_exception_if_not_found=True):
        """Return the Player object for the given `name`
        Raise an exception or just return `None` depending on `raise_exception_if_not_found`
        """
        player_regex = (r'\<a href="(?P<player_link>/{}/Player[^ ]+playerId=(?P<player_id>\d+)&[^ ]+)" .*{}'
                        .format(self.PLAYERS_LINK, name))
        if match := re.search(player_regex, players_list_page.text):
            player = Player(name, link=match.group("player_link"),
                            player_id=match.group("player_id"))
            self._download_player_info_into(player)
        elif raise_exception_if_not_found:
            raise RuntimeError("could not find any player based on '{}'!"
                               .format(player_regex))
        else:
            player = None

        return player

    def _download_team_finance_page(self):
        """Return the team-finance-page's html response object"""
        team_finance_url_suffix = "{}{}".format(self.TEAM_FINANCE_LINK, self.team.id)
        return self._open_link(team_finance_url_suffix)

    def download_team(self):
        """Return the Team object for our beloved team
        Raise an exception or just return `None` depending on `raise_exception_if_not_found`
        """
        finance_page = self._download_team_finance_page()

        total_pattern = self.DICTIONARY["total"].translate_to(self.language)
        total = FindState()
        reserves_pattern = self.DICTIONARY["board_reserves"].translate_to(self.language)
        reserves = FindState()
        money_pattern = r"(?P<value>[0-9][0-9 ]+) {}".format(self.currency)

        for byte_line in finance_page.iter_lines():
            string_line = _bytes_to_string(byte_line)

            _find_after_a_start_match(total_pattern, money_pattern, string_line,
                                      total)
            _find_after_a_start_match(reserves_pattern, money_pattern, string_line,
                                      reserves)
            if total.found() and reserves.found():
                break

        self.team.finance.total = total.get_int_or_raise_and_try_dumping_page_error(
            "Failed to find total", "total", finance_page, total_pattern
        )
        self.team.finance.board_reserves = reserves.get_int_or_raise_and_try_dumping_page_error(
            "Failed to find reserves", "reserves", finance_page, reserves_pattern
        )

        return self.team
