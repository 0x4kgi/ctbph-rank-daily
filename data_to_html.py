import json
from datetime import datetime
import logging
from scripts.json_player_data import (
    MappedPlayerDataCollection,
    MappedScoreData,
    MappedScoreDataCollection,
    get_comparison_and_mapped_data,
    get_data_at_date,
    get_sorted_dict_on_stat,
    map_player_data, ComparisonAndMappedData
)

import argparse
import scripts.general_utils as util
import scripts.html_utils as html
from scripts.logging_config import setup_logging


def generate_html_from_player_data(
        data: MappedPlayerDataCollection,
        data_difference: MappedPlayerDataCollection = None,
        timestamp: float = 0.0,
        test: bool = False,
        output_file: str = 'docs/index.html',
) -> str:
    rows = ''

    def td(content) -> str:
        return html.elem('td', content)

    def avatar(user_id) -> str:
        image = html.elem(tag_name='img', **{
            'src': f'https://a.ppy.sh/{user_id}',
            'loading': 'lazy'
        })
        return td(image)

    def difference_td(user_id, stat) -> str:
        if data_difference is None:
            return td(data[user_id].get(stat))

        current = data[user_id].get(stat)
        compare = data_difference[user_id].get(stat, 0)

        if stat in ['acc', 'pp']:
            compare = round(compare, 2)

        change = ''
        if compare:
            change = html.elem('sup',
                               '+' if compare > 0 else '',
                               str(compare),
                               **{'class': 'increase' if compare > 0 else 'decrease'}
                               )

        if stat in ['acc']:
            return td(f'{current:.2f}%{change}')
        else:
            return td(f'{current:,}{change}')

    for user_id in data:
        tr_class_list = []

        pic = avatar(user_id)
        rank = difference_td(user_id, 'country_rank')
        ign = td(data[user_id]['ign'])
        pp = difference_td(user_id, 'pp')
        acc = difference_td(user_id, 'acc')
        pc = difference_td(user_id, 'play_count')
        x = difference_td(user_id, 'rank_x')
        s = difference_td(user_id, 'rank_s')
        a = difference_td(user_id, 'rank_a')

        if data_difference[user_id]['new_entry']:
            tr_class_list.append('new-entry')

        if data_difference[user_id]['country_rank'] > 0:
            tr_class_list.append('rank-up')
        elif data_difference[user_id]['country_rank'] < 0:
            tr_class_list.append('rank-down')

        rows += html.table_row(
            rank, pic, ign, pp, acc, pc, x, s, a,
            **{
                # TODO: this is ew, if possible clean this up, ty
                'class': ' '.join(tr_class_list) if len(tr_class_list) else None
            }
        ) + '\n'

    formatted_time = util.timestamp_utc_offset(
        timestamp=timestamp,
        time_offset=8,
        time_format="%Y-%m-%d %H:%M:%S"
    )

    def total_stat(data, key) -> int:
        return sum([data[i][key] for i in data if data[i][key] > 0])

    # what the fuck
    # get_sorted_dict_on_stat returns a dict,
    # but you cannot get_sorted_dict_on_stat().items()[0] this
    # so to get the first element, cast it to a list and since an element is a tuple
    # discard the first since it's just the user_id, and we only need the dict
    # and then just do normal dict[key] to get relevant values
    # unsure if this will die if some random bullshit happens, we will see
    _, top_pp_gain = list(get_sorted_dict_on_stat(data_difference, 'pp', True).items())[0]
    _, top_pc_gain = list(get_sorted_dict_on_stat(data_difference, 'play_count', True).items())[0]
    _, top_rank_gain = list(get_sorted_dict_on_stat(data_difference, 'country_rank', True).items())[0]

    # TODO: i don't like how this ended up at all, clean up please
    # IT LOOKS SO BAD!!
    replacements = {
        'updated_at': formatted_time,
        'pp_gain': '{:,}'.format(round(top_pp_gain.get('pp', -1))),
        'pp_name': top_pp_gain.get('ign', 'nobody'),
        'rank_gain': '{:,}'.format(top_rank_gain.get('country_rank', -1)),
        'rank_name': top_rank_gain.get('ign', 'nobody'),
        'pc_gain': '{:,}'.format(top_pc_gain.get('play_count', -1)),
        'pc_name': top_pc_gain.get('ign', 'nobody'),
        'pp_total': round(total_stat(data_difference, 'pp'), 2),
        'pc_total': '{:,}'.format(total_stat(data_difference, 'play_count')),
        'rows': rows,
    }

    return stuff_to_html_templates(
        template='docs/main-page.template.html',
        output_path=output_file,
        test=test,
        **replacements,
    )


def gather_player_data(
        base_date=datetime.now(),
        compare_date_offset=1,
        country='PH',
        mode='fruits',
        test=False,
) -> ComparisonAndMappedData | None:
    processed_data = get_comparison_and_mapped_data(base_date, compare_date_offset, country, mode, test)
    latest_mapped_data = processed_data.latest_mapped_data
    comparison_mapped_data = processed_data.comparison_mapped_data

    if latest_mapped_data is None:
        logger.info('Cannot get latest data as of now.')
        return None

    if comparison_mapped_data is None:
        logger.info('Cannot get comparison data as of now.')
        return None

    return processed_data


def make_players_list_page(
        country: str = 'PH',
        mode: str = 'fruits',
        option: str = 'yesterday',
        test: bool = False
) -> None:
    logger.info('Starting making player list page')
    options = {
        # (timedelta, file_name_output)
        # TODO: make the base dir only a single instance
        'yesterday': (1, 'docs/index.html'),
        'week': (7, 'docs/weekly.html'),
        'month': (30, 'docs/monthly.html'),
        'year': (365, 'docs/yearly.html'),

        # TODO: compare from start of month, year, etc..
    }

    day_offset, output_file = options.get(option, None)

    if day_offset is None:
        logger.warning('Pick a valid option. [yesterday, week, monthly]')
        return

    player_data = gather_player_data(
        base_date=datetime.now(),
        compare_date_offset=day_offset,
        country=country, mode=mode, test=test,
    )

    if player_data is None:
        logger.warning('Player data is incomplete, will not make player HTML data.')
        return

    generate_html_from_player_data(
        data=player_data.latest_mapped_data,
        data_difference=player_data.data_difference,
        timestamp=player_data.latest_data_timestamp,
        output_file=output_file,
        test=test,
    )


def make_player_activity_leaderboards_page(
        country: str,
        mode: str,
        test: bool,
):
    player_data = gather_player_data(
        base_date=datetime.now(),
        compare_date_offset=1,  # yesterday for now
        country=country, mode=mode, test=test,
    )

    if player_data is None:
        logger.warning('Player data is incomplete, will not make player activity leaderboard page.')
        return

    stats_list: list[str] = [
        'country_rank',
        'global_rank',
        'pp',
        'acc',
        'play_count',
        'play_time',
        'ranked_score',
        'total_hits',
    ]

    sorted_stats: dict[str, MappedPlayerDataCollection] = {
        stat: get_sorted_dict_on_stat(
            data=player_data.data_difference, stat=stat, highest_first=True
        )
        for stat in stats_list
    }

    # this is temporary lol
    def avatar(user_id) -> str:
        return html.elem(tag_name='img', **{
            'src': f'https://a.ppy.sh/{user_id}',
            'loading': 'lazy'
        })

    def row_td(content) -> str:
        return html.elem('td', content)

    def row(
            gain,
            avatar,
            user_name,
            old,
            new,
    ) -> str:
        return html.elem('tr',
                         row_td(str(gain)),
                         row_td(avatar),
                         row_td(user_name),
                         row_td(str(old)),
                         row_td('→'),
                         row_td(str(new)),
                         )

    html_rows: dict[str, str] = {}

    for stat in stats_list:
        logger.debug('getting the: ' + stat)
        above_zero = {
            # sorted_stats[stat] returns all players, adding [i] will pinpoint the player
            i: sorted_stats[stat][i]
            # looks goofy but it makes sense
            for i, data in list(sorted_stats[stat].items())[:50]  # capping to 50
            if data[stat] > 0
        }
        if len(above_zero) >= 50:
            logger.warning(f'{stat} hit max limit of 50')

        rows: list[str] = []

        for user_id in above_zero:
            stat_gain = number_format_on_stat(stat, above_zero[user_id].get(stat, -1))
            old_value = number_format_on_stat(stat, player_data.comparison_mapped_data[user_id].get(stat, -1))
            new_value = number_format_on_stat(stat, player_data.latest_mapped_data[user_id].get(stat, -1))

            row_string = row(
                gain=stat_gain,
                avatar=avatar(user_id),
                user_name=above_zero[user_id].get('ign', 'unknown user'),
                old=old_value,
                new=new_value,
            )

            rows.append(row_string)

        html_rows[stat] = '\n'.join(rows)

    output_file = stuff_to_html_templates(
        template='docs/activity-ranking.template.html',
        output_path='docs/activity-ranking.html',
        test=test,
        ph_rank_rows=html_rows['country_rank'],
        global_rank_rows=html_rows['global_rank'],
        pp_rows=html_rows['pp'],
        acc_rows=html_rows['acc'],
        play_count_rows=html_rows['play_count'],
        play_time_rows=html_rows['play_time'],
        ranked_score_rows=html_rows['ranked_score'],
        total_hits_rows=html_rows['total_hits'],
    )
    logger.debug(output_file)


def number_format_on_stat(stat: str, number: int | float) -> str:
    # i forgor which
    if stat in ['acc', 'accuracy']:
        return f'{number:,.2f}'

    if stat in ['ranked_score', 'total_hits']:
        return util.simplify_number(number)

    if stat in ['play_time']:
        return util.format_duration(number)

    return f'{number:,}'


def stuff_to_html_templates(
        template: str,
        output_path: str,
        test: bool,
        **variables,
) -> str:
    if test:
        output_path = 'tests/' + output_path

    output_file = html.create_page_from_template(
        template_path=template,
        output_path=output_path,
        **variables
    )

    return output_file


def generate_html_from_pp_data(
        data: MappedScoreDataCollection,
        test: bool = False,
) -> str:
    def td(content) -> str:
        return html.elem('td', str(content))

    def img(user_id) -> str:
        return html.elem(
            'img',
            src=f'https://a.ppy.sh/{user_id}',
            loading='lazy'
        )

    def map_icon(beatmap_id: int) -> str:
        return html.elem(
            'img',
            src=f'https://assets.ppy.sh/beatmaps/{beatmap_id}/covers/list.jpg',
            loading='lazy'
        )

    def score_link(score_id: str, score: MappedScoreData) -> str:
        pp = score['score_pp']
        if score['score_type'] == 'old':
            # TODO: remove hardcoded mode in link
            link = f'https://osu.ppy.sh/scores/fruits/{score_id}'
        else:
            link = f'https://osu.ppy.sh/scores/{score_id}'

        return html.elem(
            'a',
            str(round(pp, 2)),
            href=link,
            target='_new',
        )

    rows = []

    for i in data:
        # im too lazy to type more
        d: MappedScoreData = data[i]

        pp = td(score_link(i, d))
        avatar = td(img(d['user_id']))
        player = td(d['user_name'])
        grade = td(d['score_grade'])
        song_icon = td(map_icon(d['beatmapset_id']))
        song = td(d['beatmapset_title'])
        diff = td(d['beatmap_version'])
        sr = td(d['beatmap_difficulty'])
        acc = td(round(d['accuracy'] * 100, 2))
        combo = td(d['max_combo'])
        miss = td(d['count_miss'])
        mods = td(d['score_mods'])

        rows.append(html.table_row(
            pp, avatar, player, grade, song_icon, song, diff, sr, acc, combo, miss, mods
        ))

    return stuff_to_html_templates(
        template='docs/pp-list.template.html',
        output_path='docs/pp-rankings.html',
        test=test,
        title='PP rankings for the day',
        rows='\n'.join(rows),
    )


def make_pp_records_page(
        country: str = 'PH',
        mode: str = 'fruits',
        test: bool = False,
) -> None:
    latest_timestamp = datetime.now()

    raw_scores = get_data_at_date(
        date=latest_timestamp.strftime('%Y/%m/%d'),
        country=country,
        mode=mode,
        file_type='pp-records',
        test=test,
    )

    if raw_scores is None:
        logger.info('Cannot get pp score list at the moment.')
        return

    mapped_scores: MappedScoreDataCollection = map_player_data(raw_scores)

    generate_html_from_pp_data(data=mapped_scores, test=test)


def run(
        country: str = 'PH',
        mode: str = 'fruits',
        option: str = 'yesterday',
        test: bool = False,
        skip_list: bool = False,
        skip_pp: bool = False,
        skip_activity: bool = False,
) -> None:
    if not skip_list:
        make_players_list_page(
            country=country,
            mode=mode,
            option=option,
            test=test
        )
    else:
        logger.info('Skipping making the player list.')

    if not skip_pp:
        make_pp_records_page(
            country=country,
            mode=mode,
            test=test
        )
    else:
        logger.info('Skipping making the pp records list.')

    if not skip_activity:
        make_player_activity_leaderboards_page(
            country=country,
            mode=mode,
            test=test,
        )
    else:
        logger.info('Skipping making activity leaderboard page.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Generate page from fetched data, requires leaderboard_scrape.py to be ran first!')

    parser.add_argument('--mode', type=str, default='fruits',
                        help='Define what mode, uses the parameters used on osu site.')
    parser.add_argument('--country', type=str, default='PH',
                        help='What country to make a page from. Uses 2 letter country codes.')
    parser.add_argument('--range', type=str, default='yesterday', help='What would be the comparison date to be done.')
    parser.add_argument('--test', action='store_true', help='Just do tests')
    parser.add_argument('--skip-list', action='store_true')
    parser.add_argument('--skip-pp', action='store_true')
    parser.add_argument('--skip-activity', action='store_true')

    args = parser.parse_args()

    if args.test:
        logger = setup_logging(level=logging.DEBUG)
    else:
        logger = setup_logging()

    run(
        country=args.country,
        mode=args.mode,
        option=args.range,
        test=args.test,
        skip_list=args.skip_list,
        skip_pp=args.skip_pp,
        skip_activity=args.skip_activity,
    )
