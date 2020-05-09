# coding=utf-8
"""Automate my hattrick player status monitoring"""
import common
from excel import Excel
from hattrick import Hattrick


def _update(args):
    """Update all _existing_ monitored stuff we care about"""
    read_only = getattr(args, common.READ_ONLY_ARG)
    ht = Hattrick(args.currency, args.user, args.password)  # pylint: disable=invalid-name
    xl = Excel(args.spreadsheet, read_only)  # pylint: disable=invalid-name
    with ht, xl:
        team = ht.download_team()
        print(team)
        xl.update_team(team)
        print()

        players_list_page = ht.download_player_list_page()  # only download once
        for name in xl.monitored_players_names():
            player = ht.download_player_by_name(name, players_list_page)
            print(player)
            xl.update_player(player)
            print()


def main():
    """parse args and perform the automation"""
    parser = common.cli_arg_parser()
    args = parser.parse_args()

    pause = getattr(args, common.PAUSE_ARG)
    common.run_and_maybe_pause_at_the_end(pause, _update, args)


if __name__ == "__main__":
    main()
