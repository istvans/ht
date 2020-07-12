# coding=utf-8
"""The interface between the scraper and a persistence module
This is the collection of all the info we scrape from the web or get from the
command line/the user
"""
from datetime import datetime
from enum import Enum
import re

import common


NUM_AUCTION_DAYS = 3
UNKNOWN_STR = "Ismeretlen"


class Age:  # pylint: disable=too-few-public-methods
    """A hattrick player's age is represented as years and days.
    Note: one year is 112 days for them.
    """
    STRING_FORMAT = r"(?P<years>\d+):(?P<days>\d+)"
    # If a player is 17 years 111 days old today, he is going to be 18 years and
    # 0 days old tomorrow.
    MAX_DAYS = 112

    def __init__(self, years=None, days=None):
        self.years = years
        self.days = days

    def __bool__(self):
        """Return True if this is a valid age"""
        return ((isinstance(self.years, int) and isinstance(self.days, int))
                and (16 < self.years < 142)
                and (0 <= self.days < self.MAX_DAYS))

    def __str__(self):
        """Return the readable stringification"""
        return "age:'{}' years '{}' days".format(self.years, self.days)

    @classmethod
    def parse_from_string(cls, string):
        """Parse a valid age from string or raise a ValueError"""
        if match := re.match(cls.STRING_FORMAT, string):
            years = int(match.group("years"))
            days = int(match.group("days"))
        else:
            raise ValueError("'{}' cannot be interpreted as a valid age (pattern:'{}')"
                             .format(string, cls.STRING_FORMAT))
        age = Age(years, days)
        if not age:
            raise ValueError("'{}' does not seem valid".format(age))
        return age


class NationalPlayerStatus:  # pylint: disable=too-few-public-methods
    """A hattrick player can be national team player prospect (NTPP),
    national team player (NTP) or none
    """

    def __init__(self, is_national_team_player_prospect, is_national_team_player):
        if is_national_team_player_prospect and is_national_team_player:
            raise ValueError("A player cannot be an NTPP and NTP at the same time!")
        self.is_national_team_player_prospect = is_national_team_player_prospect
        self.is_national_team_player = is_national_team_player

    def __str__(self):
        """Return the readable stringification"""
        return "NTP:{} NTPP:{}".format(
            self.is_national_team_player,
            self.is_national_team_player_prospect,
        )


class ConvertibleEnum(Enum):
    """An enum that can be parsed from string and interpreted as a bool"""

    @classmethod
    def parse_from_string(cls, string):
        """Parse a valid value from the string or raise a ValueError"""
        try:
            value = cls[string]
        except KeyError:
            raise ValueError("'{}' cannot be interpreted as {}"
                             .format(string, cls)) from None
        return value

    @classmethod
    def choices(cls):
        """Return a nicely formatted list of possible values"""
        return tuple(elem.name for elem in cls)

    def __bool__(self):
        """True if non-zero"""
        return self != self.Unknown  # pylint: disable=no-member


class Source(ConvertibleEnum):
    """The possible origin of a player"""
    Unknown = UNKNOWN_STR
    Market = "Piac"
    Academy = "Akadémia"
    Lottery = "Lottó"


class Speciality(ConvertibleEnum):
    """A player's possible speciality"""
    Unknown = UNKNOWN_STR
    Nothing = None
    Technical = "Technikás"
    Quick = "Gyors"
    Head = "Jól fejelő"
    Powerful = "Erőteljes"
    Unpredictable = "Kiszámíthatatlan"
    Resilient = "Ellenálló"
    Support = "Csapatjátékos"


class StrInt:  # pylint: disable=too-few-public-methods
    """An object with equally valid string and integer representations"""

    def __init__(self, string, integer):
        self.string = string
        self.integer = integer

    def __str__(self):
        """Just return the string representation"""
        return self.string


class Ability(ConvertibleEnum):
    """A player's potential ability level"""
    Divine = StrInt("isteni", 20)
    Utopian = StrInt("csodás", 19)
    Magical = StrInt("varázslatos", 18)
    Mythical = StrInt("legendás", 17)
    Extra_terrestrial = StrInt("földöntúli", 16)
    Titanic = StrInt("titáni", 15)
    Supernatural = StrInt("természetfeletti", 14)
    World_class = StrInt("világklasszis", 13)
    Magnificent = StrInt("lenyűgöző", 12)
    Brilliant = StrInt("ragyogó", 11)
    Outstanding = StrInt("kiemelkedő", 10)
    Formidable = StrInt("nagyszerű", 9)
    Excellent = StrInt("remek", 8)
    Solid = StrInt("jó", 7)
    Passable = StrInt("megfelelő", 6)
    Inadequate = StrInt("középszerű", 5)
    Weak = StrInt("gyenge", 4)
    Poor = StrInt("csapnivaló", 3)
    Wretched = StrInt("pocsék", 2)
    Disastrous = StrInt("katasztrofális", 1)
    Non_existent = StrInt("nem létező", 0)
    Unknown = StrInt(UNKNOWN_STR.lower(), -1)

    def __str__(self):
        """Just return the value's string representation"""
        return self.value.string  # pylint: disable=no-member

    @classmethod
    def parse_from_int(cls, integer):
        """Parse a valid value from the integer or raise a ValueError"""
        for member in cls:
            if member.value.integer == integer:
                return member
        raise ValueError("'{}' cannot be interpreted as {}"
                         .format(integer, cls))


class Skillz:
    """The skills we are interested in"""

    def __init__(self,  # pylint: disable=too-many-arguments
                 playmaking=None, winger=None, passing=None, scoring=None,
                 speciality=Speciality.Unknown):
        self.playmaking = playmaking
        self.winger = winger
        self.passing = passing
        self.scoring = scoring
        self.speciality = speciality

    def __str__(self):
        """Return the readable stringification of the skillz"""
        return ("pm:'{}' w:'{}' pa:'{}' sc:'{}' spec:{}"
                .format(self.playmaking, self.winger, self.passing, self.scoring,
                        self.speciality.name))

    def __bool__(self):
        """Return True if, apart from speciality!, we have a sensible value for all"""
        skillz_are_defined = (
            s is not None
            for s in (self.playmaking, self.winger, self.passing, self.scoring))
        return all(skillz_are_defined)


class PlayerMixin:  # pylint: disable=too-few-public-methods
    """Collection of useful player related things"""

    def _ensure_valid_value(self,  # pylint: disable=too-many-arguments
                            attribute_name, args, is_undefined_fn, parse_from_string,
                            choices):
        """A value defined on the command line always takes precedence over the
        originally scraped value (if there was any). The user's direct input
        is used as a last resort
        may raise UserInputWasCancelled
        """
        attribute = getattr(self, attribute_name)
        cli_value = getattr(args, attribute_name)
        if cli_value is None:
            if is_undefined_fn(attribute):
                value = common.get_from_user(attribute_name, parse_from_string, choices)
            else:
                value = None
        elif isinstance(cli_value, str):
            value = parse_from_string(cli_value)
        else:
            value = cli_value

        if value is not None:
            setattr(self, attribute_name, value)


class ExtraPlayerInfo(PlayerMixin):
    """Extra details for a player"""
    DATE_FORMAT = "%d/%m/%Y"

    def __init__(self):
        self.skillz = Skillz()
        self.source = Source.Unknown
        self.stars = None
        self.reserve_price = None
        self.buy_price = None
        self.arrival = None

    def __str__(self):
        """Return the readable stringification of this extra info"""
        if self:
            source_name = self.source.name  # pylint: disable=no-member
            stringified = (
                "\nsource:{} stars:'{}' {} rp:'{}' bp:'{}' arrival:'{}'"
                .format(source_name, self.stars, self.skillz, self.reserve_price,
                        self.buy_price, self.arrival)
            )
        else:
            stringified = ""
        return stringified

    def __bool__(self):
        """Return True if the instance has the bare minimum"""
        return bool(self.skillz)

    def fill_from_cli_or_user(self, args) -> None:
        """Fill in the missing extra info (if there's any...) using _ensure_valid_value
        may raise UserInputWasCancelled
        """
        float_number_choices = "a float number"
        self._ensure_valid_value(
            "source", args, lambda x: not x, Source.parse_from_string,
            Source.choices())
        self._ensure_valid_value(
            "stars", args, lambda x: x is None, float, float_number_choices)
        self._ensure_valid_value(
            "reserve_price", args, lambda x: x is None, float, float_number_choices)
        self._ensure_valid_value(
            "buy_price", args, lambda x: x is None, float, float_number_choices)
        self._ensure_valid_value(
            "arrival", args, lambda x: x is None,
            lambda s: datetime.strptime(s, self.DATE_FORMAT),
            self.DATE_FORMAT)


class Player(PlayerMixin):  # pylint: disable=too-many-instance-attributes
    """A collection of all the info we care about a hattrick player"""

    def __init__(self, name, link, player_id):
        self.name = name
        self.link = link
        self.id = player_id  # pylint: disable=invalid-name
        self.age = Age()
        self.tsi = None
        self.ntp_status = NationalPlayerStatus(False, False)
        self.sell_base_price = None
        self.form = Ability.Unknown
        self.stamina = Ability.Unknown
        self.extra = ExtraPlayerInfo()

    def __str__(self):
        """Return the readable stringification of a player"""
        form_name = self.form.name  # pylint: disable=no-member
        stamina_name = self.stamina.name  # pylint: disable=no-member
        return (
            "'{}' (id:'{}') {} TSI:'{}' {} SBP:'{}' form:{} stamina:{} {}"
            .format(
                self.name, self.id, self.age, self.tsi, self.ntp_status,
                self.sell_base_price, form_name, stamina_name, self.extra
            )
        )

    def fill_from_cli_or_user(self, args) -> None:
        """Fill in any missing info or override info from the command line
        may raise UserInputWasCancelled
        """
        self._ensure_valid_value(
            "age", args, lambda x: not x, Age.parse_from_string,
            Age.STRING_FORMAT)
        self._ensure_valid_value(
            "tsi", args, lambda x: x is None, int, "an int number")
        self._ensure_valid_value(
            "sell_base_price", args, lambda x: x is None, float, "a float number")
        self.extra.fill_from_cli_or_user(args)


class Finance:  # pylint: disable=too-few-public-methods
    """Team finance info"""

    def __init__(self, total=None, board_reserves=None):
        self.total = total
        self.board_reserves = board_reserves

    def __str__(self):
        """Return the readable stringification of this object"""
        return (
            "total:{} board reserves:{}"
            .format(self.total, self.board_reserves)
        )


class Team:  # pylint: disable=too-few-public-methods
    """A collection of all the info we care about the team"""

    def __init__(self, team_id, name):
        self.id = team_id  # pylint: disable=invalid-name
        self.name = name
        self.finance = Finance()

    def __str__(self):
        """Return the readable stringification of this object"""
        return (
            "'{}' (id:'{}') {}"
            .format(self.name, self.id, self.finance)
        )
