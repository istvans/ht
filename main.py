# coding=utf-8
"""The goal of this module is to automate my hattrick player status monitoring
"""
from hattrick import Hattrick


with Hattrick() as ht:
    team = ht.download_team()
    print(team)
    # TODO update excel

    players_list_page = ht.download_player_list_page()  # only download once
    # TODO get list of players from excel
    for name in ("Matar Beyal", "Alexandru Daina", "Jutas Rácz", "Fawwaz Al Dailami"):
        player = ht.download_player_by_name(name, players_list_page)
        print(player)
        # TODO update excel
