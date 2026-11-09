"""课堂二维码自动扫描：抓教室画面 → 识别二维码 → 输出扫码结果。

原理：
    直播间页面的 HTML 里藏着一份 `args` 配置，里面有 main（教室摄像头）、
    ppt（投影/大屏）等几路画面地址。用 ffmpeg 抓一帧，交给 OpenCV 解码表，
    得到的就是二维码里的真实内容（和微信扫一扫读到的一样）。

依赖：Python 3.9+ / ffmpeg（PATH 里能找到）/ opencv-python / numpy / pycryptodome / requests
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

try:  # 避免在 GBK 控制台里因为个别字符直接崩掉
    sys.stdout.reconfigure(errors='replace')
    sys.stderr.reconfigure(errors='replace')
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
from classroom import Classroom  # noqa: E402

BASE = Path(__file__).resolve().parent
HITS = BASE / 'qr_hits'


def load_json(name):
    path = BASE / name
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf8'))
    except Exception:
        return {}


def today_room(timetable):
    """从 timetable.json 里猜此刻/下一节该扫哪个教室。"""
    entries = timetable if isinstance(timetable, list) else timetable.get('slots') or []
    now = datetime.now()
    weekday = now.isoweekday()
    minutes = now.hour * 60 + now.minute
    upcoming = None
    for entry in entries:
        if entry.get('weekday') != weekday:
            continue
        try:
            start_min = int(str(entry.get('start')).split(':')[0]) * 60 + int(str(entry.get('start')).split(':')[1])
            end_min = int(str(entry.get('end')).split(':')[0]) * 60 + int(str(entry.get('end')).split(':')[1])
        except Exception:
            continue
        room = entry.get('room') or entry.get('classroom')
        if not room:
            continue
        if start_min <= minutes <= end_min:
            return room, entry.get('course')
        if start_min > minutes and (upcoming is None or start_min < upcoming[0]):
            upcoming = (start_min, room, entry.get('course'))
    if upcoming:
        return upcoming[1], upcoming[2]
    return None, None


class Scanner:
    def __init__(self, streams, log=print):
        self.streams = streams
        self.detector = cv2.QRCodeDetector()
        self.log = log

    def grab(self, channel):
        stream = self.streams.get(channel) or next(iter(self.streams.values()), None)
        if not stream:
            return None
        tmp = Path(tempfile.gettempdir()) / f'qrframe_{int(time.time() * 1000)}.png'
        done = subprocess.run(
            ['ffmpeg', '-hide_banner', '-nostdin', '-y', '-t', '4', '-i', stream,
             '-frames:v', '1', str(tmp)],
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
        if done.returncode != 0 or not tmp.exists():
            return None
        image = cv2.imread(str(tmp))
        try:
            tmp.unlink()
        except Exception:
            pass
        return image

    def decode(self, image):
        """多策略识别：原图 → 放大 2 倍 → 灰度自适应二值化。"""
        if image is None:
            return []
        candidates = [image]
        if max(image.shape[:2]) < 1600:
            candidates.append(cv2.resize(image, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC))
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                       cv2.THRESH_BINARY, 31, 10)
        candidates.append(cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR))

        found = []
        for candidate in candidates:
            try:
                ok, texts, _points, _ = self.detector.detectAndDecodeMulti(candidate)
            except Exception:
                ok, texts = False, []
            if ok:
                found.extend(text.strip() for text in texts or [] if text and text.strip())
            if not found:
                try:
                    text, _points, _ = self.detector.detectAndDecode(candidate)
                except Exception:
                    text = ''
                if text and text.strip():
                    found.append(text.strip())
            if found:
                break
        return list(dict.fromkeys(found))


def save_hit(image, texts, save_dir):
    save_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%m%d_%H%M%S')
    image_path = save_dir / f'qr_{stamp}.png'
    text_path = save_dir / f'qr_{stamp}.txt'
    cv2.imwrite(str(image_path), image)
    text_path.write_text('\n'.join(texts), encoding='utf8')
    return image_path, text_path


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='抓课堂画面并识别其中的二维码',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='示例：\n'
               '  python scan_qr.py --url "https://psp-zelda.chaoxing.com/vri-zelda/mobile_live?..."\n'
               '  python scan_qr.py --room 9107 --channels ppt,main\n'
               '  python scan_qr.py --stream demo.png --once\n')
    parser.add_argument('--url', help='直播间链接')
    parser.add_argument('--room', help='教室号，配合 rooms.json 使用')
    parser.add_argument('--channels', default='', help='轮流扫描多路画面，例如 ppt,main')
    parser.add_argument('--channel', default='ppt', choices=['main', 'ppt', 'other'],
                        help='只扫某一路时用（默认 ppt）')
    parser.add_argument('--interval', type=float, default=2.0, help='扫描间隔秒数，默认 2')
    parser.add_argument('--timeout', type=int, default=300, help='最长扫描秒数，0 = 一直扫')
    parser.add_argument('--once', action='store_true', help='只抓一次')
    parser.add_argument('--open', action='store_true', help='识别到链接就用默认浏览器打开')
    parser.add_argument('--copy', action='store_true', help='把结果复制到剪贴板')
    parser.add_argument('--user', help='超星账号（需要登录的链接才用）')
    parser.add_argument('--password', help='超星密码')
    parser.add_argument('--stream', help='调试用：直接给视频流或本地文件')
    parser.add_argument('--save-dir', default=str(HITS), help='命中截图的保存目录')
    args = parser.parse_args(argv)

    save_dir = Path(args.save_dir)

    if args.stream:
        streams = {'main': args.stream}
        info = '本地测试流'
    else:
        url = args.url
        if not url:
            rooms = load_json('rooms.json')
            room = args.room
            if not room:
                room, course = today_room(load_json('timetable.json'))
                if room:
                    print(f'课表推断：{room} {course or ""}', flush=True)
            if not room:
                print('请用 --url 或 --room 指定教室，并准备 rooms.json。', flush=True)
                return 1
            links = rooms.get(room) or []
            if not links:
                print(f'rooms.json 里没有 {room} 的链接。', flush=True)
                return 1
            url = links[0]
            print(f'教室 {room}：{url[:90]}…', flush=True)
        info = '直播间'

        user = args.user or os.environ.get('CHAOXING_USER') or load_json('config.json').get('user', '')
        password = args.password or os.environ.get('CHAOXING_PASS') or load_json('config.json').get('password', '')
        page = Classroom(url, user, password, log=lambda m: print(f'  [{m}]', flush=True))
        streams = page.streams
        print(f'  场次 {page.speech_id}  教室 {page.room}  课程 {page.course}  '
              f'可用画面 {list(streams)}', flush=True)

    if not streams:
        print('这个页面没有可用的画面地址。', flush=True)
        return 1

    scanner = Scanner(streams)
    channels = [c.strip() for c in (args.channels or args.channel).split(',') if c.strip()]
    deadline = time.time() + args.timeout if args.timeout else float('inf')
    rounds, hits = 0, []

    while time.time() < deadline:
        rounds += 1
        channel = channels[(rounds - 1) % len(channels)]
        image = scanner.grab(channel)
        if image is None and channel != 'main':
            image = scanner.grab('main')
        texts = scanner.decode(image)
        stamp = datetime.now().strftime('%H:%M:%S')

        if texts:
            for text in texts:
                print(f'[{stamp}] [OK] 识别到二维码：{text}', flush=True)
            image_path, text_path = save_hit(image, texts, save_dir)
            print(f'           截图：{image_path}', flush=True)
            print(f'           结果：{text_path}', flush=True)
            hits = texts
            break

        print(f'[{stamp}] 第 {rounds} 次（{channel}）：未发现二维码', flush=True)
        if args.once:
            break
        time.sleep(max(args.interval, 0.2))

    if not hits:
        print('扫描结束，没有识别到二维码。', flush=True)
        return 2

    result = hits[0]
    if args.copy:
        try:
            subprocess.run(['powershell', '-NoProfile', '-Command', 'Set-Clipboard -Value $args[0]', result],
                           capture_output=True)
            print('已复制到剪贴板。', flush=True)
        except Exception:
            pass
    if args.open and result.lower().startswith(('http://', 'https://')):
        subprocess.run(['powershell', '-NoProfile', '-Command', 'Start-Process $args[0]', result])
    print('\n扫码结果：' + result, flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
