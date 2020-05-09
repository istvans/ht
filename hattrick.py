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

from data import Player, Age, NationalPlayerStatus, Team, Skillz, Speciality


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


def _parse_login_status(response):
    """Parse login status from the response page and return True for logged in
    and False otherwise"""
    login_failure_pattern = r"ucLogin_lblFailureText"
    return not re.search(login_failure_pattern, response.text)


def _ensure_login(response):
    """If login failed based on the `response` raise a RuntimeError"""
    logged_in = _parse_login_status(response)
    if logged_in:
        print("we're in! :)")
    else:
        _raise_and_try_dumping_page_error(
            "Failed to log in (maybe the username/password is wrong!?)", "login", response
        )


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
                and (value := getattr(self, language)) is not None
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
                        "Unsupported page language id: '{}'"
                        " The supported language ids are '{}'"
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
        self.in_block = False
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

    def find_in_a_block(self, block_pattern, value_pattern, text):
        """Find the `block_pattern` then look for the `value_pattern` and, once found,
        save it into this instance
        """
        if self.in_block and self.found_value is None:
            if match := re.search(value_pattern, text):
                self.found_value = match.group("value")
                self.in_block = False

        if self.found_value is None and re.search(block_pattern, text):
            self.in_block = True


class BlockValueFindState(FindState):
    """Preserve state for block-value pattern-finding algorithms with multi-phases"""

    def __init__(self, block_pattern, value_pattern):
        super(BlockValueFindState, self).__init__()
        self.block_pattern = block_pattern
        self.value_pattern = value_pattern

    def find_in(self, text):
        """Find the `block_pattern` then look for the `value_pattern` and, once found,
        save it into this instance
        """
        self.find_in_a_block(self.block_pattern, self.value_pattern, text)


def _find_values_in_blocks(search, page):
    """Find the things specified in the `search` dictionary on the `page`
    The expected search dictionary format is this:
    {
        '<thing>': BlockValueFindState,
    }
    Return whether all of them was found
    """
    found_all = False
    for byte_line in page.iter_lines():
        string_line = _bytes_to_string(byte_line)

        found_all = True
        for pattern in search.values():
            pattern.find_in(string_line)
            if not pattern.found():
                found_all = False

        if found_all:
            break
    return found_all


def _parse_int_values_from_blocks_into(container, search, page):
    """Find the things specified in the `search` dictionary on the `page`
    and convert them into int values to be stored in the `container`
    """
    _find_values_in_blocks(search, page)

    for (attribute, string_value) in search.items():
        not_found_error_message = "Failed to find '{}'".format(attribute)
        int_value = string_value.get_int_or_raise_and_try_dumping_page_error(
            not_found_error_message, attribute, page, string_value.block_pattern
        )
        setattr(container, attribute, int_value)


def _parse_player_tsi(player_page):
    """Parse and return the player's TSI or raise a RuntimeError"""
    search = {
        "tsi": BlockValueFindState(block_pattern=r"TSI</td>",
                                   value_pattern=r">(?P<value>[^><]+)</td>"),
    }
    _find_values_in_blocks(search, player_page)

    tsi = search["tsi"]
    return tsi.get_int_or_raise_and_try_dumping_page_error(
        "Failed to find the player's tsi", "tsi",
        player_page, tsi.value_pattern,
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


def _get_user():
    """Get a username from the user"""
    user = None
    while user is None:
        try:
            user = input("Username: ")
        except SyntaxError:
            user = None
        if user == "":
            user = None
        if user is None:
            print("Please enter a valid username")
    return user


def _get_from_user_if_none(maybe_none_value, get_from_user_function):
    """Get the value from the user if it was None originally"""
    if maybe_none_value is None:
        value = get_from_user_function()
    else:
        value = maybe_none_value
    return value


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

    USER_FIELD = "ctl00$CPContent$ucLogin$txtUserName"
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
        "spec:technical": LanguageDependentText(
            hungarian="Technikás",
            english="Technical",
        ),
        "spec:quick": LanguageDependentText(
            hungarian="Gyors",
            english="Quick",
        ),
        "spec:head": LanguageDependentText(
            hungarian="Jól fejelő",
            english="Head",
        ),
        "spec:powerful": LanguageDependentText(
            hungarian="Erőteljes",
            english="Powerful",
        ),
        "spec:unpredictable": LanguageDependentText(
            hungarian="Kiszámíthatatlan",
            english="Unpredictable",
        ),
        "spec:resilient": LanguageDependentText(
            hungarian="Ellenálló",
            english="Resilient",
        ),
        "spec:support": LanguageDependentText(
            hungarian="Csapatjátékos",
            english="Support",
        ),
        "avg_star_value": LanguageDependentText(
            hungarian=r"Átlagos csillagérték (?P<stars>[0-9.]+)",
            english=None,
        )
    }

    def __init__(self, currency, user=None, password=None):
        """Initialise a new session before login"""
        if currency is None:
            raise ValueError("The currency cannot be None")

        self.currency = currency
        self.user = user
        self.password = password
        self.server_id = None
        self.team = None
        self.language = None
        self.logged_in = False

    def _translate_to(self, key, language):
        """Translate the value for `key` from `self.DICTIONARY` to the specified
        language.
        """
        return self.DICTIONARY[key].translate_to(language)

    def _translate_to_page_language(self, key):
        """Translate the value for `key` from `self.DICTIONARY` to the page's
        language.
        """
        return self._translate_to(key, self.language)

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
            print("Connecting... ", end="")
            response = HtLink.request(self.MAIN_PAGE, use_headers=False)
            print("done")

            self.LOGIN_FORM[self.USER_FIELD] = _get_from_user_if_none(self.user, _get_user)
            self.LOGIN_FORM[self.PASSWORD_FIELD] = _get_from_user_if_none(self.password, getpass)
            self._fill_in_form_with_lookup_values(response, self.LOGIN_FORM)

            print("Login... ", end="")
            response = HtLink.request(self.LOGIN_PAGE, method="post", data=self.LOGIN_FORM)
            response.raise_for_status()
            _ensure_login(response)
            self.logged_in = True

            server_pattern = r"^(?P<server_url>.*www(?P<server_id>\d+)\.hattrick\.org)"
            if match := re.search(server_pattern, response.url):
                HtLink.SERVER_URL = match.group("server_url")
                HtLink.SERVER_ID = int(match.group("server_id"))
                team_id = _parse_team_id(response)
                team_name = self._parse_team_name_by_id(response, team_id)
                self.team = Team(team_id=team_id, name=team_name)
                self.language = LanguageDependentText.find_language_in(response)
                HtLink.APP_ERROR_PATTERN = self._translate_to_page_language("app_error")
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

        search = {
            "sell_base_price": BlockValueFindState(block_pattern=avg_price_block_pattern,
                                                   value_pattern=price_pattern),
        }
        _find_values_in_blocks(search, price_estimation_page)

        sell_base_price = search["sell_base_price"]
        return sell_base_price.get_int_or_raise_and_try_dumping_page_error(
            "Failed to find the player's base sell price", "bsp",
            price_estimation_page, sell_base_price.value_pattern,
        )

    def _parse_speciality(self, player_page):
        """Parse the speciality of the player, if any"""
        spec_tags = {
            self._translate_to_page_language(tag): tag
            for tag in self.DICTIONARY if "spec:" in tag
        }
        spec_tags_pattern = r"(?P<spec>{})".format('|'.join(spec_tags.keys()))
        if match := re.search(spec_tags_pattern, player_page.text):
            tag = spec_tags[match.group("spec")]
            english_name_of_spec = self._translate_to(tag, "english")
            speciality = Speciality.parse_from_string(english_name_of_spec)
        else:
            speciality = Speciality.Nothing
        return speciality

    def _parse_player_skillz(self, player_page):
        """Parse the player's skillz"""
        skill_pattern = r"level='(?P<value>[0-9]+)'"
        search = {
            "playmaking": BlockValueFindState(block_pattern="PlayerSkills_trPlaymaker",
                                              value_pattern=skill_pattern),
            "winger": BlockValueFindState(block_pattern="PlayerSkills_trWinger",
                                          value_pattern=skill_pattern),
            "passing": BlockValueFindState(block_pattern="PlayerSkills_trPasser",
                                           value_pattern=skill_pattern),
            "scoring": BlockValueFindState(block_pattern="PlayerSkills_trScorer",
                                           value_pattern=skill_pattern),
        }
        skillz = Skillz()
        _parse_int_values_from_blocks_into(skillz, search, player_page)

        skillz.speciality = self._parse_speciality(player_page)

        return skillz

    def _parse_player_stars(self, player_page):
        """If there were previous games for this players, we'll return his star-rating
        Otherwise, we'll return None.
        """
        star_pattern = self._translate_to_page_language("avg_star_value")
        if match := re.search(star_pattern, player_page.text):
            stars = float(match.group("stars"))
        else:
            stars = None
        return stars

    def _download_player_info_into(self, player):
        """Download all the info we need into the specified `player`"""
        response = HtLink.request(player.link)
        player.age = self._parse_player_age(response)
        player.tsi = _parse_player_tsi(response)
        player.ntp_status = self._parse_national_team_player_status(response)
        player.sell_base_price = self._parse_player_sell_base_price(response)
        player.extra.skillz = self._parse_player_skillz(response)
        player.extra.stars = self._parse_player_stars(response)

    def download_player_by_name(self, name, players_list_page, raise_exception_if_not_found=True):
        """Return the Player object for the given `name`
        Raise an exception or just return `None` depending on `raise_exception_if_not_found`
        """
        player_regex = ((r'\<a href="(?P<player_link>/{}/Player[^ ]+'
                         r'playerId=(?P<player_id>\d+)&[^ ]+)" title="[^"]+">{}')
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
        """Return the Team object for our beloved team"""
        finance_page = self._download_team_finance_page()

        money_pattern = r"(?P<value>[0-9][0-9 ]+) {}".format(self.currency)
        total_pattern = self._translate_to_page_language("total")
        reserves_pattern = self._translate_to_page_language("board_reserves")
        search = {
            "total": BlockValueFindState(block_pattern=total_pattern,
                                         value_pattern=money_pattern),
            "board_reserves": BlockValueFindState(block_pattern=reserves_pattern,
                                                  value_pattern=money_pattern),
        }
        _parse_int_values_from_blocks_into(self.team.finance, search, finance_page)

        return self.team
