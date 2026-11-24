"""超星智慧教室直播间页面解析（独立最小实现，不依赖主程序）。

只做三件事：
1. 打开直播间链接，必要时用账号密码登录；
2. 从页面 HTML 里取出 `args` 配置；
3. 给出 main / ppt / other 三路画面地址。
"""
import base64
import json
import re
from urllib.parse import parse_qs, unquote, urlparse

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

KEY = b'u2oh6Vu^HWe4_AES'
LIVE_HOST = 'https://psp-zelda.chaoxing.com'
LOGIN_URL = 'https://passport2.chaoxing.com/fanyalogin'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')


def encrypt(value: str) -> str:
    cipher = AES.new(KEY, AES.MODE_CBC, KEY)
    return base64.b64encode(cipher.encrypt(pad(value.encode(), 16))).decode()


def page_args(page: str):
    """从页面里抠出 `args = {...}` 这个 JS 对象。"""
    match = re.search(r'\bargs\s*=\s*', page)
    if not match:
        return None
    return json.JSONDecoder().raw_decode(page[match.end():].lstrip())[0]


def looks_like_login(response) -> bool:
    return ('passport2.chaoxing.com' in response.url
            or 'fanyalogin' in response.text
            or 'id="refer"' in response.text)


def refer_of(response):
    match = re.search(r'id="refer"[^>]*value="([^"]*)"', response.text)
    if match:
        return match.group(1)
    query = parse_qs(urlparse(response.url).query)
    values = query.get('refer') or []
    return values[0] if values else None


class Classroom:
    """一个直播间对应一个实例。"""

    def __init__(self, url, username='', password='', log=None, timeout=25):
        self.log = log or (lambda message: None)
        self.url = url
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': UA, 'Accept-Language': 'zh-CN,zh;q=0.9'})

        response = self.session.get(url, timeout=timeout, allow_redirects=True)
        if looks_like_login(response):
            if not (username and password):
                raise RuntimeError('这个链接需要登录，请用 --user 和 --password 提供账号密码')
            self.log('需要登录，正在用账号密码登录')
            refer = refer_of(response)
            if not refer:
                raise RuntimeError('登录页缺少 refer 参数')
            payload = {
                'fid': '-1',
                'uname': encrypt(username),
                'password': encrypt(password),
                'refer': refer,
                't': 'true',
                'forbidotherlogin': '0',
                'validate': '',
                'doubleFactorLogin': '0',
                'independentId': '',
                'independentNameId': '',
            }
            login = self.session.post(LOGIN_URL, data=payload, timeout=timeout)
            try:
                result = login.json()
            except Exception:
                raise RuntimeError('登录接口返回异常：' + login.text[:120])
            if not result.get('status'):
                raise RuntimeError(result.get('msg2') or result.get('mes') or '登录失败')
            self.log('登录成功')
            target = unquote(result.get('url') or url)
            response = self.session.get(target, timeout=timeout, allow_redirects=True)

        response.raise_for_status()
        self.page_url = response.url or url
        self.session.headers['Referer'] = self.page_url
        self.args = page_args(response.text)
        if not self.args:
            raise RuntimeError('页面里没有直播配置（链接失效，或这场直播已经结束）')

    @property
    def speech(self):
        return self.args.get('speech') or {}

    @property
    def settings(self):
        return self.speech.get('settings') or {}

    @property
    def speech_id(self):
        return self.speech.get('speechId') or 'unknown'

    @property
    def course(self):
        settings = self.settings
        return (settings.get('coursename') or settings.get('courseName') or '').strip() or '-'

    @property
    def room(self):
        return self.settings.get('skdd') or '-'

    @property
    def streams(self):
        """{类型: 流地址}，类型一般是 main（教室摄像头）/ ppt（投影）/ other。"""
        result = {}
        for video in self.speech.get('videos') or []:
            url = video.get('mobile') or video.get('realHttp')
            if url:
                result[video.get('type') or 'main'] = url
        return result
