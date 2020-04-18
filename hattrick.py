# coding=utf-8
"""My little Hattrick scraper module
Supported Hattrick page languages:
    - Hungarian
Supported users:
    - Stevensson
"""
from getpass import getpass
import io
from pprint import pprint
import re
import sys

import requests

from data import Player, Age, NationalPlayerStatus, Team


def _dump_a_page_to_file(page, file_name):
    """Dump the text of `page` into `file_name`
    It might raise all kinds of io errors...
    """
    with io.open(file_name, mode="w", encoding="utf-8") as dump_file:
        dump_file.write(page.text)


def _raise_and_try_dumping_page_error(
        base_error_message, dump_suffix, page, regex=None):
    """Raise a runtime error and try to dump the `page` to
    crashdump.`dump_suffix`.html
    `base_error_message` will be extended with (the optional) `regex` and the
    dump file name if dumping succeeded
    """
    saved_page_file = "crashdump.{}.html".format(dump_suffix)
    try:
        _dump_a_page_to_file(page, saved_page_file)
    except Exception:  # pylint: disable=broad-except
        saved_page_file = None

    if regex is not None:
        error_message = "{} regex: '{}'".format(base_error_message, regex)
    else:
        error_message = base_error_message

    if saved_page_file is not None:
        error_message = ("{} this page dump might help: '{}'").format(
            error_message, saved_page_file
        )

    raise RuntimeError(error_message)


class HtLink:
    """The hattrick link abstraction"""

    APP_ERROR_PATTERN = None
    HEADER = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
                      " (KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36"
    }
    SERVER_ID = None
    SERVER_URL = None
    SESSION = None

    @classmethod
    def _ensure_no_app_error(cls, response, data):
        """Check whether the response contains an application error
        If so, raise an exception
        """
        if cls.APP_ERROR_PATTERN is not None:
            if re.search(cls.APP_ERROR_PATTERN, response.text):
                if data is not None:
                    pprint("We've tried to use this data:{}".format(data))
                _raise_and_try_dumping_page_error(
                    "'{}'!".format(cls.APP_ERROR_PATTERN), "app_error", response
                )

    @classmethod
    def request(cls, link, use_headers=True, method="get", data=None):
        """Request the download of the link using the live session and return
        the HTML response
        Raise an exception if the final response code isn't 200 (OK).
        The `link` must be a complete URL while `SERVER_URL` is None
        and must be a sub-link otherwise
        If `method` is not a valid session method, AttributeError will be
        raised
        """
        session_method = getattr(cls.SESSION, method)

        server_url = cls.SERVER_URL
        link_url = "{}/{}".format(server_url, link) if server_url is not None else link

        params = {}
        if use_headers:
            params["headers"] = cls.HEADER
        if data is not None:
            params["data"] = data

        response = session_method(link_url, **params)
        response.raise_for_status()
        cls._ensure_no_app_error(response, data)

        return response

    @classmethod
    def start_session(cls):
        """Start the live session"""
        cls.SESSION = requests.Session()

    @classmethod
    def close_session(cls):
        """End the live session"""
        if cls.SESSION is not None:
            cls.SESSION.__exit__()


class NoDefinitionInThisLanguageError(Exception):
    """Should be raised if we try to get the translation for a supported language
    in LanguageDependentText, but it is None
    """


class LanguageDependentText:
    """Store all the translations of a text in these 'language fields'"""

    SUPPORTED_LANGUAGES = ["hungarian", "english"]

    def __init__(self, **kwargs):
        for language in self.SUPPORTED_LANGUAGES:
            setattr(self, language, kwargs[language])

    def translate_to(self, language):
        """Get the text in the specified language
        If the language is not supported -> AttributeError
        If the language is supported, but the text is None ->
        NoDefinitionInThisLanguageError
        """
        text = getattr(self, language)
        if text is None:
            available_definitions = {
                language: value
                for language in dir(self)
                if not language.startswith("__")
                and (value:= getattr(self, language)) is not None
            }
            error_message = ("{} available definitions: {}"
                             .format(language, available_definitions))
            raise NoDefinitionInThisLanguageError(error_message)
        return text

    @classmethod
    def find_language_in(cls, page):
        """Find and return the page's language or raise a RuntimeError"""
        page_language_regex = r'lang="(?P<language_id>[^"]+)"'
        if match := re.search(page_language_regex, page.text):
            page_language_pattern_to_script_language_mapping = {
                "hu": cls.SUPPORTED_LANGUAGES[0],
                "en": cls.SUPPORTED_LANGUAGES[1],
            }
            language_id = match.group("language_id")
            if language_id not in page_language_pattern_to_script_language_mapping:
                supported_language_ids = " ".join(
                    page_language_pattern_to_script_language_mapping.keys()
                )
                raise RuntimeError(
                    (
                        "Failed to detect the page's language from '{}'"
                        " The supported language codes are '{}'"
                    ).format(language_id, supported_language_ids)
                )

            language = page_language_pattern_to_script_language_mapping[language_id]
        else:
            _raise_and_try_dumping_page_error(
                "Failed to detect the page's language",
                "lang",
                page,
                page_language_regex,
            )
        return language


def _remove_witespace(raw_string):
    """Return a new string without any whitespace"""
    return "".join(raw_string.split())


def _string_to_int(raw_string):
    """Convert a string that contain numbers and optionally whitespace to int
    """
    return int(_remove_witespace(raw_string))


def _bytes_to_string(bytes_value):
    r"""Convert `bytes_value` to string by also replacing the following HTML
    characters:
    \xa0 -> " "
    &nbsp; -> " "
    """
    return (bytes_value.decode("utf-8").replace("\xa0", " ")
            .replace("&nbsp;", " "))


class FindState:
    """Preserve state for a find algorithm with multiple phases"""

    def __init__(self):
        self.lets_find = False
        self.found_value = None

    def found(self):
        """Return if the searched value was found"""
        return self.found_value is not None

    def get_int_or_raise_and_try_dumping_page_error(
            self, base_error_message, dump_suffix, page, regex=None):
        """As its name suggests: it tries to return the `found_value` as `int`, or
        if it wasn't found, call _raise_and_try_dumping_page_error()
        If converting the found value to `int` fails, some kind of exception
        will be raised too
        """
        if self.found():
            int_value = _string_to_int(self.found_value)
        else:
            _raise_and_try_dumping_page_error(
                base_error_message, dump_suffix, page, regex
            )
        return int_value


def _find_in_a_block(block_pattern, value_pattern, text, find_state):
    """Find the `block_pattern` then look for the `value_pattern` and, once found,
    save it into `find_state`
    """
    if not isinstance(find_state, FindState):
        raise TypeError(
            "find_state must be of type FindState and not '{}'"
            .format(type(find_state))
        )

    if find_state.lets_find and find_state.found_value is None:
        if match := re.search(value_pattern, text):
            find_state.found_value = match.group("value")

    if find_state.found_value is None and re.search(block_pattern, text):
        find_state.lets_find = True


def _parse_player_tsi(player_page):
    """Parse and return the player's TSI or raise a RuntimeError"""
    tsi_on_next_line_pattern = r"TSI</td>"
    tsi_value_pattern = r">(?P<value>[^><]+)</td>"

    tsi = FindState()
    for byte_line in player_page.iter_lines():
        string_line = _bytes_to_string(byte_line)

        _find_in_a_block(
            tsi_on_next_line_pattern, tsi_value_pattern, string_line, tsi
        )
        if tsi.found():
            break

    return tsi.get_int_or_raise_and_try_dumping_page_error(
        "Failed to find the player's tsi", "tsi",
        player_page, tsi_value_pattern,
    )


def _parse_team_id(page):
    """Parse and return the team id or raise a RuntimeError"""
    team_id_pattern = r"currentTeamId=(?P<team_id>\d+)"
    cookie_text = page.request.headers["Cookie"]
    if match := re.search(team_id_pattern, cookie_text):
        team_id = int(match.group("team_id"))
    else:
        raise RuntimeError(
            "Unexpected Cookie: '{}'".format(page.request.headers["Cookie"])
        )
    return team_id


def _lookup_value_on_page_for_key(page, key):
    """Look up and return the current value of `key` on the page or
    raise a RuntimeError"""
    regex = r'{}.*value="(?P<value>[^"]+)"'.format(key)
    if match := re.search(regex, page.text):
        value = match.group("value")
    else:
        _raise_and_try_dumping_page_error(
            "Failed to find the value of '{}'".format(key), "value",
            page, regex
        )
    return value


def _update_form_with_dynamic_value(page, key, form):
    """Look up the `value` for the `key` on the `page` and update the `form`
    with it at `key`"""
    value = _lookup_value_on_page_for_key(page, key)
    form[key] = value


class Hattrick:
    """Represent a Hattrick login-session"""

    MAIN_PAGE = "https://www.hattrick.org/en/"

    LOGIN_PAGE = "https://www.hattrick.org/en/Startpage3.aspx"

    # we lookup up the value of these when we POST request forms
    LOOKUP_FORM_FIELD_KEYS = (
        "__EVENTVALIDATION",
        "__VIEWSTATE",
        "__VIEWSTATEGENERATOR",
    )

    TOKEN = (";;System.Web.Extensions, Version=4.0.0.0, Culture=neutral,"
             " PublicKeyToken=31bf3856ad364e35:en-GB:ad6c4949-7f20-401f-a40f"
             "-4d4c52722104:ea597d4b:b25378d2")

    LOGIN_FORM = {
        "ctl00_sm_HiddenField": TOKEN,
        "__EVENTTARGET": "ctl00$CPContent$ucLogin$butLogin",
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

    # MAYDO properly support English too
    DICTIONARY = {
        "age": LanguageDependentText(
            hungarian=r"(?P<years>\d+) éves és (?P<days>\d+) napos",
            english=None,
        ),
        "nt": LanguageDependentText(
            hungarian="válogatott csapatának is tagja!",
            english=None,
        ),
        "nt_prospect": LanguageDependentText(
            hungarian="nemzeti csapatának jelöltje", english=None,
        ),
        "app_error": LanguageDependentText(
            hungarian="Alkalmazáshiba",
            english=None,
        ),
        "avg_price_block": LanguageDependentText(
            hungarian=">Átlagérték<",
            english=None,
        ),
        "total": LanguageDependentText(
            hungarian="Összesen:",
            english=None,
        ),
        "board_reserves": LanguageDependentText(
            hungarian="Az igazgatóság tartaléka:",
            english=None,
        ),
    }

    def __init__(self, currency="eFt"):
        """Initialise a new session before login"""
        self.currency = currency
        self.server_id = None
        self.team = None
        self.language = None
        self.logged_in = False

    def _translate_to_page_language(self, key):
        """Translate the value for `key` from `self.DICTIONARY` to the page's
        language.
        """
        return self.DICTIONARY[key].translate_to(self.language)

    def _parse_team_name_by_id(self, page, team_id):
        """Parse and return the team's name or raise a RuntimeError"""
        regex = r'a href="/{}{}" title="(?P<name>[^"]+)"'.format(
            self.TEAM_LINK_PATTERN, team_id
        )
        if match := re.search(regex, page.text):
            name = match.group("name")
        else:
            _raise_and_try_dumping_page_error(
                "Failed to find the team's name!", "team_name", page, regex,
            )

        return name

    def _fill_in_form_with_lookup_values(self, page, form):
        """Look up the values for `LOOKUP_FORM_FIELD_KEYS` on the `page` and
        fill in the `form`
        """
        for key in self.LOOKUP_FORM_FIELD_KEYS:
            _update_form_with_dynamic_value(page, key, form)

    def __enter__(self):
        """Login to Hattrick
        If any step fail, an exception is raised so if we managed to enter, we are in.
        In case of an exception, __exit__ will run, so don't worry.
        """
        try:
            HtLink.start_session()
            response = HtLink.request(self.MAIN_PAGE, use_headers=False)

            self.LOGIN_FORM[self.PASSWORD_FIELD] = getpass()
            self._fill_in_form_with_lookup_values(response, self.LOGIN_FORM)

            response = HtLink.request(self.LOGIN_PAGE, method="post", data=self.LOGIN_FORM)
            response.raise_for_status()
            server_pattern = r"^(?P<server_url>.*www(?P<server_id>\d+)\.hattrick\.org)"
            if match := re.search(server_pattern, response.url):
                HtLink.SERVER_URL = match.group("server_url")
                HtLink.SERVER_ID = int(match.group("server_id"))
                team_id = _parse_team_id(response)
                team_name = self._parse_team_name_by_id(response, team_id)
                self.team = Team(team_id=team_id, name=team_name)
                self.language = LanguageDependentText.find_language_in(response)
                HtLink.APP_ERROR_PATTERN = self._translate_to_page_language("app_error")
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
            HtLink.request(self.LOGOUT_LINK)
            self.logged_in = False
            print("We're out! :)")

        HtLink.close_session()

    def download_player_list_page(self):
        """Return the player list page html response object"""
        players_url_suffix = "{}/?TeamID={}".format(self.PLAYERS_LINK, self.team.id)
        return HtLink.request(players_url_suffix)

    def _parse_player_age(self, player_page):
        """Parse and return the player's age or raise a RuntimeError"""
        age_pattern = self._translate_to_page_language("age")
        if match := re.search(age_pattern, player_page.text):
            age = Age(int(match.group("years")), int(match.group("days")))
        else:
            _raise_and_try_dumping_page_error(
                "Failed to find the player's age", "age", player_page, age_pattern
            )
        return age

    def _parse_national_team_player_status(self, player_page):
        """Parse and return the player's ::NationalPlayerStatus"""
        nt_pattern = self._translate_to_page_language("nt")
        nt_player = bool(re.search(nt_pattern, player_page.text))

        nt_prospect_pattern = self._translate_to_page_language("nt_prospect")
        nt_player_prospect = bool(re.search(nt_prospect_pattern,
                                            player_page.text))

        return NationalPlayerStatus(
            is_national_team_player=nt_player,
            is_national_team_player_prospect=nt_player_prospect,
        )

    def _load_more_transfers(self, page, link):
        """Load more transfers using the original `page` and return this "updated page"
        which supposed to list more transfers
        """
        self._fill_in_form_with_lookup_values(page, self.LOAD_MORE_TRANSFERS_FORM)
        return HtLink.request(link, method="post", data=self.LOAD_MORE_TRANSFERS_FORM)

    def _download_sell_price_etimation_page(self, player_page):
        """Return the requested page's html response object"""
        regex = r'a href="/(?P<link>{}[^"]+)"'.format(self.TRANSFER_COMPARE_LINK)
        if match := re.search(regex, player_page.text):
            link = match.group("link")
            price_estimation_page = HtLink.request(link)

            there_is_more_transfer_to_load = re.search(
                self.FURTHER_TRANSFERS_LINK_ID, price_estimation_page.text
            )
            if there_is_more_transfer_to_load:
                price_estimation_page = self._load_more_transfers(
                    price_estimation_page, link
                )
        else:
            _raise_and_try_dumping_page_error(
                "Failed to find the player's transfer compare link",
                "tcl",
                player_page,
                regex,
            )
        return price_estimation_page

    def _parse_player_sell_base_price(self, player_page):
        """Parse and return the player's base sell price
        To do that we need to navigate to the sell price estimation page first
        """
        price_estimation_page = self._download_sell_price_etimation_page(player_page)

        avg_price_block_pattern = self._translate_to_page_language("avg_price_block")
        price_pattern = r'right transfer-compare-bid">(?P<value>[0-9 ]+) {}</th>'.format(
            self.currency
        )

        sell_base_price = FindState()
        for byte_line in price_estimation_page.iter_lines():
            string_line = _bytes_to_string(byte_line)

            _find_in_a_block(
                avg_price_block_pattern, price_pattern, string_line, sell_base_price
            )
            if sell_base_price.found():
                break

        return sell_base_price.get_int_or_raise_and_try_dumping_page_error(
            "Failed to find the player's base sell price",
            "bsp",
            price_estimation_page,
            price_pattern,
        )

    def _download_player_info_into(self, player):
        """Download all the info we need into the specified `player`"""
        response = HtLink.request(player.link)
        player.age = self._parse_player_age(response)
        player.tsi = _parse_player_tsi(response)
        player.ntp_status = self._parse_national_team_player_status(response)
        player.sell_base_price = self._parse_player_sell_base_price(response)

    def download_player_by_name(
            self, name, players_list_page, raise_exception_if_not_found=True):
        """Return the Player object for the given `name`
        Raise an exception or just return `None` depending on `raise_exception_if_not_found`
        """
        player_regex = ((r'\<a href="(?P<player_link>/{}/Player[^ ]+'
                         r'playerId=(?P<player_id>\d+)&[^ ]+)" .*{}')
                        .format(self.PLAYERS_LINK, name))
        if match := re.search(player_regex, players_list_page.text):
            player = Player(
                name,
                link=match.group("player_link"),
                player_id=match.group("player_id"),
            )
            self._download_player_info_into(player)
        elif raise_exception_if_not_found:
            raise RuntimeError(
                "could not find any player based on '{}'!".format(player_regex)
            )
        else:
            player = None

        return player

    def _download_team_finance_page(self):
        """Return the team-finance-page's html response object"""
        team_finance_url_suffix = "{}{}".format(self.TEAM_FINANCE_LINK, self.team.id)
        return HtLink.request(team_finance_url_suffix)

    def download_team(self):
        """Return the Team object for our beloved team
        Raise an exception or just return `None` depending on `raise_exception_if_not_found`
        """
        finance_page = self._download_team_finance_page()

        total_pattern = self._translate_to_page_language("total")
        total = FindState()
        reserves_pattern = self.DICTIONARY["board_reserves"].translate_to(self.language)
        reserves = FindState()
        money_pattern = r"(?P<value>[0-9][0-9 ]+) {}".format(self.currency)

        for byte_line in finance_page.iter_lines():
            string_line = _bytes_to_string(byte_line)

            _find_in_a_block(total_pattern, money_pattern, string_line, total)
            _find_in_a_block(
                reserves_pattern, money_pattern, string_line, reserves
            )
            if total.found() and reserves.found():
                break

        self.team.finance.total = total.get_int_or_raise_and_try_dumping_page_error(
            "Failed to find total", "total", finance_page, total_pattern
        )
        self.team.finance.board_reserves = reserves.get_int_or_raise_and_try_dumping_page_error(
            "Failed to find reserves", "reserves", finance_page, reserves_pattern
        )

        return self.team
