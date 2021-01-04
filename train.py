import math

import click


def level_coeff(level):
    if level < 9:
        return 16.289 * math.exp(-0.1396 * level)
    else:
        return (54.676 / level) - 1.438


def coach_coeff(level):
    coeff_of_coach_level = {
        8: 1.0375,
        7: 1.0000,
        6: 0.9200,
        5: 0.8324,
        4: 0.7343,
    }
    return coeff_of_coach_level[level]


def assistant_coeff(level):
    coeff_of_assistant_level = {
        10: 1.350,
        9: 1.315,
        8: 1.280,
        7: 1.245,
        6: 1.210,
        5: 1.175,
        4: 1.140,
        3: 1.105,
        2: 1.070,
        1: 1.035,
        0: 1.000,
    }
    return coeff_of_assistant_level[level]


def intensity_coeff(percent):
    return percent / 100.0


def stamina_coeff(percent):
    return (100.0 - percent) / 100.0


COEFF_OF_TRAIN_TYPE = {
    "GK": 0.0510,
    "DF": 0.0288,
    "PM": 0.0336,
    "W": 0.0480,
    "PS": 0.0360,
    "SC": 0.0324,
    "SP": 0.01470,
    "SC_and_PS": 0.0150,
    "FirstPS": 3.15,
    "ZoneDF": 1.38,
    "WingAttack": 0.0312,
}


def train_coeff(train_type, full_train_position):
    c = COEFF_OF_TRAIN_TYPE[train_type]
    if full_train_position:
        ratio = 1.0
    else:
        backround_ratio_of_train_type = {
            "DF": 1 / 6,
            "PM": 1 / 8,
            "W": 1 / 8,
            "PS": 1 / 6,
            "SC": 1 / 6,
            "FirstPS": 1 / 6,
            "ZoneDF": 1 / 6,
            "WingAttack": 5 / 39,
        }
        ratio = backround_ratio_of_train_type[train_type]
    return c * ratio


def age_coeff(age):
    return 54.0 / (age + 37.0)


def play_time_coeff(play_time=90):
    """This would be rather complicated, but for our purposes, we can just use the default."""
    return play_time / 90.0


def training_progress(level, coach, assist, intensity, stamina, train_type, full, age):
    lvl = level_coeff(level)
    c = coach_coeff(coach)
    a = assistant_coeff(assist)
    i = intensity_coeff(intensity)
    s = stamina_coeff(stamina)
    t = train_coeff(train_type, full)
    ag = age_coeff(age)
    pt = play_time_coeff()
    progress = lvl * c * a * i * s * t * ag * pt
    if progress > 1.0:
        progress = 1.0
    return progress


@click.group()
@click.option("-l", "--level", required=True, type=int, help="Current skill level.")
@click.option("-c", "--coach", required=True, type=int, help="The coach's level.")
@click.option("-a", "--assist", required=True, type=int,
              help="The coach assistants' level (assuming both are on the same level).")
@click.option("-i", "--intensity", required=True, type=int,
              help="The training intensity in percentage e.g. 100 for 100%.")
@click.option("-s", "--stamina", required=True, type=int, help="The stamina percentage e.g. 10 for 10%.")
@click.option("-t", "--train-type", required=True, help="The training type.",
              type=click.Choice(COEFF_OF_TRAIN_TYPE.keys(), case_sensitive=False))
@click.option("--full/--background", default=True, help="Whether the player is trained on a full training slot.")
@click.option("-g", "--age", required=True, type=int, help="The player's age.")
@click.pass_context
def train(ctx, level, coach, assist, intensity, stamina, train_type, full, age):
    progress = training_progress(level, coach, assist, intensity, stamina, train_type, full, age)

    ctx.ensure_object(dict)
    ctx.obj["level"] = level
    ctx.obj["coach"] = coach
    ctx.obj["assist"] = assist
    ctx.obj["intensity"] = intensity
    ctx.obj["stamina"] = stamina
    ctx.obj["train_type"] = train_type
    ctx.obj["full"] = full
    ctx.obj["age"] = age
    ctx.obj["progress"] = progress


def next_level_after_a_season(level, coach, assist, intensity, stamina, train_type, full, age):
    season_weeks = 16
    for season in range(season_weeks):
        progress = training_progress(level, coach, assist, intensity, stamina, train_type, full, age)
        level += progress
        age += 1
    return math.floor(level)


@train.command()
@click.pass_context
def weekly(ctx):
    """Print the fractional training progress after a week"""
    progress = ctx.obj["progress"]
    print(progress)


@train.command()
@click.pass_context
def season(ctx):
    """Print the reached level after a season of training"""
    level = ctx.obj["level"]
    coach = ctx.obj["coach"]
    assist = ctx.obj["assist"]
    intensity = ctx.obj["intensity"]
    stamina = ctx.obj["stamina"]
    train_type = ctx.obj["train_type"]
    full = ctx.obj["full"]
    age = ctx.obj["age"]
    next_level = next_level_after_a_season(level, coach, assist, intensity, stamina, train_type, full, age)
    print(next_level)


if __name__ == '__main__':
    train()
