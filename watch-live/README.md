# 课堂实况直播（单窗口播放器）

> 点一下，弹出一个播放窗口看**当前这节课**的教室画面，关掉就结束。
> 不常驻、不轮询、不判断有没有课——只在启动那一下看一次课表。

属于 [ZUFE_AutoLiveSign](https://github.com/zhirui0322/qiandao) 的配套小工具，可以单独使用。

---

## 为什么不用浏览器播

超星的直播间页面在部分场次会把播放源写成 `no_source.m3u8`（服务器没给播放源），于是页面、手机端都会报「直播已结束 / 网络连接不稳定」。但教室的摄像头其实一直在推流——只要绕过播放器，直接拉 `live.flv` 就能看。

试过的方案：

| 方案 | 结果 |
| :--- | :--- |
| 超星页面播放器 | 播放源 no_source，必黑屏 |
| 浏览器 + flv.js / MSE | MSE 挂上了，但拿不到数据 |
| 浏览器 + fMP4 直连 | 能播，但一次只服务一个连接，多开互挤 |
| **ffplay 窗口** | ✅ 稳定、流畅、有声音，延迟 1 秒左右 |

---

## 依赖

| 依赖 | 说明 |
| :--- | :--- |
| Python 3.9+ | 实测 3.13 |
| `requests` / `pycryptodome` | `pip install -r requirements.txt` |
| **ffmpeg（含 ffplay）** | 必须在 PATH 里：`winget install Gyan.FFmpeg` |

---

## 用法

双击 **`看直播.bat`** —— 打开当前这节课的画面，一个窗口，关掉即结束。

命令行：

```bash
python watch_live.py                     # 当前这节课的教室摄像头
python watch_live.py --channel ppt       # 改看投影
python watch_live.py --room 9107         # 指定教室
python watch_live.py --mute              # 静音
python watch_live.py --test-time 18:35   # 只查这个时间点上什么课
```

| 参数 | 默认 | 说明 |
| :--- | :--- | :--- |
| `--room` | 按课表取 | 指定教室号 |
| `--channel` | `main` | `main` 摄像头 / `ppt` 投影 / `other` 其他 |
| `--mute` | 关 | 静音 |
| `--test-time` | - | 调试用，只做一次课表判断 |

---

## 需要的两个文件

放在 `watch-live` 目录（或与主程序同目录）下：

**`rooms.json`** —— 教室 → 直播间链接：

```json
{ "9107": ["https://psp-zelda.chaoxing.com/vri-zelda/mobile_live?speechid=..&enc=..&pid=..&warning=false"] }
```

**`userdata/pid.txt`** —— 一行你的 `pid`（链接里那段身份标识）。如果链接本身已经带了 `pid`，这个文件可以不建。

---

## 常见问题

**打开就提示「这个教室现在可能没在推流」**
说明当前没课，或者设备关机了。换 `--channel ppt` 再试一次。

**没有课的时候点开会怎样**
会打印「现在没有课」和下一节课的时间，不会弹窗口。

**窗口一闪就没**
多半是 ffplay 拉流失败（404）。先确认是不是在上课时间。

---

## 免责声明

仅供个人学习自用，请遵守课堂纪律与平台协议。
