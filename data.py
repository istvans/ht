# coding=utf-8
"""The interface between the scraper and a persistence module
Here is the collection of all the info we scrape from the web
"""


class Age(object):
    """A hattrick player's age is represented as years and days.
    Note: one year is 112 days for them.
    """
    def __init__(self, years=None, days=None):
        self.years = years
        self.days = days
        if not ((isinstance(self.years, int) and isinstance(self.days, int))
             or (self.years is None and self.days is None)):
            raise ValueError("{} and {} do not seem a valid age".format(years, days))

    def __str__(self):
        """Return the readable stringification"""
        return "age:'{}' years '{}' days".format(self.years, self.days)

class NationalPlayerStatus(object):
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
        return "NTP:{} NTPP:{}".format(self.is_national_team_player,
                                       self.is_national_team_player_prospect,
                                      )


class Player(object):
    """A collection of all the info we care about a hattrick player"""
    def __init__(self, name, link, player_id):
        self.name = name
        self.link = link
        self.id = player_id
        self.age = Age()
        self.tsi = None
        self.ntp_status = NationalPlayerStatus(False, False)
        self.sell_base_price = None

    def __str__(self):
        """Return the readable stringification of a player"""
        return ("'{}' (id:'{}') '{}' TSI:'{}' {} SBP:{}"
                .format(self.name, self.id, self.age, self.tsi,
                        self.ntp_status, self.sell_base_price,
                       )
        )


class Finance(object):
    """Team finance info"""
    def __init__(self, total=None, board_reserves=None):
        self.total = total
        self.board_reserves = board_reserves

    def __str__(self):
        """Return the readable stringification of this object"""
        return ("total:{} board reserves:{}"
                .format(self.total, self.board_reserves)
        )


class Team(object):
    """A collection of all the info we care about the team"""
    def __init__(self, team_id, name):
        self.id = team_id
        self.name = name
        self.finance = Finance()

    def __str__(self):
        """Return the readable stringification of this object"""
        return ("'{}' (id:'{}') {}"
                .format(self.name, self.id, self.finance)
        )
