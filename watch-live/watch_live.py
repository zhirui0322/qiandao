"""课堂直播：点一下，弹出一个播放窗口，关掉就结束。

不带后台常驻，也不做“现在有没有课”的循环判断——只在启动时看一次课表，
定位到当前这节课的教室，直接开一个播放器窗口。

用法：
    python watch_live.py                   # 当前这节课的教室摄像头
    python watch_live.py --channel ppt     # 看投影
    python watch_live.py --room 9107       # 指定教室
    python watch_live.py --mute            # 静音
    python watch_live.py --test-time 18:35 # 只查这个点该看哪个教室
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
from classroom import Classroom

PID = os.environ.get('CHAOXING_PID', '')
_pid_file = BASE / 'userdata' / 'pid.txt'
if not PID and _pid_file.exists():
    PID = _pid_file.read_text('utf-8-sig').strip()
CHANNELS = {'main': '教室摄像头', 'ppt': '投影 / 大屏', 'other': '其他画面'}
SIZE = {'main': (1280, 720), 'ppt': (1100, 620), 'other': (960, 540)}

cfg = json.loads((BASE / 'userdata' / 'settings.json').read_text('utf-8-sig')) \
    if (BASE / 'userdata' / 'settings.json').exists() else {}
acc = json.loads((BASE / 'userdata' / 'account.json').read_text('utf-8-sig')) \
    if (BASE / 'userdata' / 'account.json').exists() else {}
timetable = json.loads((BASE / 'userdata' / 'timetable.json').read_text('utf-8-sig')) \
    if (BASE / 'userdata' / 'timetable.json').exists() else {}
rooms = json.loads((BASE / 'rooms.json').read_text('utf-8-sig')) \
    if (BASE / 'rooms.json').exists() else {}
if not rooms:
    rooms = timetable.get('rooms') or {}
CLASSES = [c for c in (timetable.get('classes') or [])
           if c.get('room') and c.get('start') and c.get('end')]


def to_minutes(text):
    try:
        hour, minute = str(text).split(':')[:2]
        return int(hour) * 60 + int(minute)
    except Exception:
        return None


def current_class(now=None, lead=2, tail=2):
    now = now or datetime.now()
    minutes = now.hour * 60 + now.minute
    for course in CLASSES:
        if course.get('weekday') != now.isoweekday():
            continue
        start, end = to_minutes(course['start']), to_minutes(course['end'])
        if start is None or end is None:
            continue
        if start - lead <= minutes <= end + tail:
            return course
    return None


def next_class(now=None):
    now = now or datetime.now()
    minutes = now.hour * 60 + now.minute
    for offset in range(8):
        candidates = []
        for course in CLASSES:
            if course.get('weekday') != ((now.isoweekday() + offset - 1) % 7) + 1:
                continue
            start = to_minutes(course['start'])
            if start is None:
                continue
            if offset == 0 and start <= minutes:
                continue
            candidates.append((offset * 1440 + start - minutes, course))
        if candidates:
            return min(candidates, key=lambda item: item[0])[1]
    return None


def build_url(room):
    links = rooms.get(room) or []
    if not links:
        return None
    link = links[0]
    if '/vri-zelda/index?' in link:
        link = link.replace('/vri-zelda/index?', '/vri-zelda/mobile_live?')
    if 'pid=' not in link and PID:
        link += ('&' if '?' in link else '?') + f'pid={PID}&warning=false'
    return link


def child_env():
    """ffplay 会读 http_proxy，去掉代理变量免得连不上本机/校园网。"""
    env = dict(os.environ)
    for key in ('http_proxy', 'https_proxy', 'all_proxy', 'no_proxy',
                'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY'):
        env.pop(key, None)
    return env


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--room', help='指定教室（默认按课表取当前这节课）')
    parser.add_argument('--channel', default='main', choices=list(CHANNELS),
                        help='看哪一路画面，默认 main（教室摄像头）')
    parser.add_argument('--mute', action='store_true', help='静音')
    parser.add_argument('--test-time', help='调试：按 HH:MM 判断一次后退出')
    args = parser.parse_args()

    if args.test_time:
        hour, minute = (int(part) for part in args.test_time.split(':'))
        fake = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
        course = current_class(fake)
        upcoming = next_class(fake)
        print(f'{fake:%m-%d %H:%M} 星期{fake.isoweekday()}')
        print('当前课：', f'{course["room"]} {course["start"]}–{course["end"]} {course["name"]}'
              if course else '（没有课）')
        if upcoming:
            print('下一节：', f'星期{upcoming["weekday"]} {upcoming["start"]}–{upcoming["end"]} '
                          f'{upcoming["room"]} {upcoming["name"]}')
        print('链接：', '有' if (course and build_url(course['room'])) else '无')
        return

    room = args.room
    course = None
    if not room:
        course = current_class()
        room = course['room'] if course else None
        if not room:
            upcoming = next_class()
            tip = (f'下一节是星期{upcoming["weekday"]} {upcoming["start"]} {upcoming["room"]} '
                   f'{upcoming["name"]}，到点再点一次就行。' if upcoming else '近期没有课。')
            print('现在没有课。' + tip)
            print('想临时看某个教室：python watch_live.py --room 9107')
            return

    url = build_url(room)
    if not url:
        print(f'rooms.json 里没有 {room} 的链接。')
        return

    try:
        page = Classroom(url, str(cfg.get('user') or ''), str(acc.get('password') or ''))
    except Exception as error:
        print(f'打开直播间失败：{error}')
        return

    streams = page.streams
    target = streams.get(args.channel) or streams.get('main')
    if not target:
        print('这个页面没有可用的画面。')
        return

    width, height = SIZE.get(args.channel, (1280, 720))
    title = f'{room} {CHANNELS.get(args.channel, args.channel)}'
    command = [
        'ffplay', '-hide_banner', '-loglevel', 'error',
        '-fflags', 'nobuffer', '-flags', 'low_delay',
        '-probesize', '500000', '-analyzeduration', '300000',
        '-window_title', title, '-x', str(width), '-y', str(height),
        '-autoexit',
    ]
    if args.mute:
        command += ['-volume', '0']
    command.append(target)

    label = f'{room} {course["name"]}' if course else room
    print(f'正在打开：{label} - {CHANNELS.get(args.channel, args.channel)}')
    print('关掉播放窗口就结束。')
    try:
        process = subprocess.Popen(command, env=child_env())
    except FileNotFoundError:
        print('没找到 ffplay，请先安装 ffmpeg（winget install Gyan.FFmpeg）。')
        return
    except Exception as error:
        print(f'启动播放器失败：{error}')
        return
    code = process.wait()
    if code != 0:
        print('播放器已退出：这个教室现在可能没在推流（没课或者设备关了）。')
        print('可以换一路试试：python watch_live.py --room %s --channel ppt' % room)


if __name__ == '__main__':
    main()
