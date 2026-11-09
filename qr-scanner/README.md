# 课堂二维码自动扫描器

> 抓智慧教室的实时画面，识别屏幕上的二维码，直接把**扫码结果**给你——不用掏手机、不用等播放器转圈。
>
> 属于 [ZUFE_AutoLiveSign](https://github.com/zhirui0322/qiandao) 的一个独立小工具，可以单独使用。

---

## 它解决什么问题

有些课会把签到码、问卷码、群二维码投在投影上。等你打开直播页面，往往遇到两件事：

- 手机播放器提示「网络连接不稳定」「直播已结束」；
- 或者干脆没时间看，码就被划走了。

但**页面播不了 ≠ 拿不到画面**。直播间的 HTML 里藏着一份配置，里面有教室摄像头、投影等几路**流地址**；只要用 `ffmpeg` 抓一帧下来，二维码就躺在图片里。这个工具把这一串动作自动化了。

```text
直播间链接 ──► 解析页面配置 ──► ffmpeg 抓一帧 ──► OpenCV 解码 ──► 输出扫码结果
                                  (main / ppt)      (含放大、二值化兜底)    (并复制到剪贴板)
```

识别出来的就是二维码里真实的那个链接/文本，和微信「扫一扫」读到的是同一个东西。

---

## 安装

需要三样东西：

| 依赖 | 说明 |
| :--- | :--- |
| Python 3.9+ | 建议 3.11 / 3.13 |
| [ffmpeg](https://ffmpeg.org/download.html) | **必须在 PATH 里**，命令行敲 `ffmpeg -version` 能出版本号 |
| Python 包 | `pip install -r requirements.txt` |

```bash
pip install -r requirements.txt
```

---

## 使用

### 方式一：双击 bat（最省事）

双击 `微信扫码.bat`，默认扫「今天课表里的教室」，PPT 和摄像头两路轮流扫，**扫到就停**并把结果放进剪贴板。

前提：同目录下有 `rooms.json`（格式见 `rooms.example.json`）。

### 方式二：命令行

```bash
# 直接给链接
python scan_qr.py --url "https://psp-zelda.chaoxing.com/vri-zelda/mobile_live?speechid=...&enc=..."

# 给教室号（读取 rooms.json）
python scan_qr.py --room 9107

# 只扫投影 / 只扫摄像头
python scan_qr.py --room 9107 --channel ppt
python scan_qr.py --room 9107 --channel main

# 两路轮流，2 秒一轮，最多扫 30 分钟
python scan_qr.py --room 9107 --channels ppt,main --interval 2 --timeout 1800

# 只抓一次
python scan_qr.py --room 9107 --once
```

### 参数

| 参数 | 默认 | 说明 |
| :--- | :--- | :--- |
| `--url` | - | 直播间链接 |
| `--room` | - | 教室号，配合 `rooms.json` |
| `--channel` | `ppt` | 只扫某一路：`main`（摄像头）/ `ppt`（投影）/ `other` |
| `--channels` | - | 轮流扫多路，如 `ppt,main` |
| `--interval` | `2` | 每轮间隔秒数 |
| `--timeout` | `300` | 最长扫描秒数，`0` = 一直扫 |
| `--once` | 关 | 只抓一次就走 |
| `--open` | 关 | 识别到 http(s) 链接就用默认浏览器打开 |
| `--copy` | 关 | 把结果复制到剪贴板 |
| `--user` / `--password` | - | 链接需要登录时用（也可用环境变量 `CHAOXING_USER` / `CHAOXING_PASS`，或 `config.json`） |
| `--stream` | - | 调试用：直接喂视频流或本地图片/视频 |
| `--save-dir` | `qr_hits/` | 命中截图的保存目录 |

### 输出

```text
[12:45:22] [OK] 识别到二维码：https://v.xuexi365.com/signin?act=st&id=test8899
           截图：qr_hits\qr_1109_124522.png
           结果：qr_hits\qr_1109_124522.txt

扫码结果：https://v.xuexi365.com/signin?act=st&id=test8899
```

每命中一次会存两样东西到 `qr_hits/`：**当时的截图**（万一解出来的链接需要人工核对）和**识别出的文本**。

---

## 配置 rooms.json

```json
{
  "9107": [
    "https://psp-zelda.chaoxing.com/vri-zelda/mobile_live?speechid=...&enc=...&ifnotrefresh=1&index=0&pid=...&warning=false"
  ]
}
```

两点经验：

1. **优先用 `mobile_live` 写法，不要用 `index` 写法**。`index` 是 PC 版页面，现在基本都要登录态；`mobile_live` 直接就能打开。
2. 链接里带上 `pid=...&warning=false` 可以免登录。`pid` 是你账号的身份标识，**别公开分享**。

`rooms.json` 里放多行也可以，程序用第一条。

---

## 常见问题

**Q：为什么手机打不开，这个工具却抓得到？**

手机打开的是「播放器」，播放器会检查场次时间窗（页面里的 `endtimestamp`），过期就提示「直播已结束」或直接报错。这个工具不走播放器，它直接从流地址抓帧，不受那套前端判断影响。

**Q：提示「未发现二维码」？**

- 先确认这个教室**当前在推流**（上课时间）；
- 投影没开就换 `--channel main`（摄像头）；
- 码太小/反光 → 用 `--channels ppt,main` 多轮扫描，或者把 `--interval` 调小；
- 想确认是不是画质问题，加 `--save-dir` 保留截图看看。

**Q：识别出来的是链接，但需要在微信里打开。**

把结果粘到微信「文件传输助手」发给自己，再点开即可——脚本只负责把码解开，不会替你在微信里完成操作。

**Q：链接要账号密码？**

加 `--user` / `--password`，或者在同目录建一个 `config.json`：

```json
{ "user": "你的手机号", "password": "你的密码" }
```

**Q：会不会影响我正在跑的主程序？**

不会。它只请求一次页面、抓一帧画面，不碰字幕游标，不写主程序的 `logs/`。

---

## 免责声明

仅供**个人学习与自用**，请遵守所在学校的课堂纪律与平台用户协议。不要用它代替本人上课、代签或替他人签到。因使用产生的任何后果由使用者自负。
