# coding=utf-8
"""Automate adding a newly bought player to the _monitoring system_"""
from datetime import    datetime

import common
from data import Source, ExtraPlayerInfo, Age
from excel import Excel
from hattrick import Hattrick


def _add_player(args):
    """Get all the stuff we need for a new player and add him to the monitoring system"""
    player_name = args.name
    read_only = getattr(args, common.READ_ONLY_ARG)
    ht = Hattrick(args.currency, args.user, args.password)  # pylint: disable=invalid-name
    xl = Excel(args.spreadsheet, read_only)  # pylint: disable=invalid-name
    with ht, xl:
        players_list_page = ht.download_player_list_page()
        player = ht.download_player_by_name(player_name, players_list_page)
        player.fill_from_cli_or_user(args)
        print(player)
        xl.add_player(player)


def _escape_percent_sign(string):
    """Return a string within which all percent signs are escaped"""
    return string.replace('%', "%%")


def main():
    """parse args and perform the automation"""
    parser = common.cli_arg_parser()
    parser.add_argument("-n", "--name", required=True, help="the new player's full name")
    parser.add_argument("-o", "--source", required=False,
                        choices=Source.choices(),
                        help="the new player's source (aka origin)")
    parser.add_argument("-x", "--stars", required=False, type=float,  # TODO support unknown
                        help="the new player's star rating")
    parser.add_argument("-R", "--reserve_price", required=False, type=float,  # TODO support unknown and None!
                        help="the player's initial auction price")
    parser.add_argument("-b", "--buy_price", required=False, type=float,
                        help="the player's final auction price")
    arrival_date_format = ExtraPlayerInfo.DATE_FORMAT
    arrival_date_format_string = _escape_percent_sign(arrival_date_format)
    parser.add_argument("-a", "--arrival", required=False,
                        type=lambda s: datetime.strptime(s, arrival_date_format),
                        help=("the player's arrival date in '{}' format"
                              .format(arrival_date_format_string)))  # TODO support unknown
    parser.add_argument("-A", "--age", required=False,
                        type=Age.parse_from_string,
                        help=("the player's age in '{}' format"  # TODO support unknown
                              .format(Age.STRING_FORMAT)))
    parser.add_argument("-t", "--tsi", required=False, type=int,
                        help="the player's TSI")  # TODO support unknown
    parser.add_argument("-S", "--sell_base_price", required=False, type=float,
                        help="the player's estimated average market value")
    args = parser.parse_args()

    pause = getattr(args, common.PAUSE_ARG)
    with common.maybe_pause_at_the_end(pause):
        _add_player(args)


if __name__ == "__main__":
    main()
