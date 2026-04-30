# 敬拜团歌谱阅读器

一个轻量、可离线的网页版歌谱阅读器，从 Dropbox 团队空间自动读取每周敬拜歌谱。
为 iPad Air 2（iOS 15.8 Safari）等老设备优化。

## 功能

- **自动跳本周**：打开后自动跳到最近的主日（按文件夹名 `YYYYMMDD_主理` 解析）
- **手势浏览**：左右滑动切歌、双指缩放、双击复位
- **离线缓存**：每张歌谱图片下载后存到 IndexedDB，断网也能用
- **PWA**：iPad 上"添加到主屏幕"，像 App 一样使用
- **深色背景**：敬拜灯光暗时不刺眼
- **故障兜底**：API 挂了自动用缓存，网页都崩了底部有 Dropbox 直链

## 文件结构

```
worship-app/
├── index.html      ← 单文件应用（HTML + CSS + JS 全部内联）
├── sw.js           ← Service Worker（应用离线缓存 + 自动更新）
├── manifest.json   ← PWA 清单
├── icon.png        ← 192×192 图标
├── icon-512.png    ← 512×512 图标
└── README.md       ← 这份文档
```

## 配置（已经配好了，仅供参考）

`index.html` 顶部有几个常量：

```js
const APP_KEY = '83a0si04afgfc04';                      // Dropbox App key
const REFRESH_TOKEN = 'K2PVGmaxpTEAA...';               // PKCE refresh token
const TEAM_ROOT_ID = '2615124675';                      // MILAN REVIVAL CHURCH 团队空间
const WORSHIP_PATH = '/06-办公室电脑惠普HP/敬拜团歌谱';   // 歌谱根路径（团队空间内）
```

如果以后路径变了或要换 Dropbox App，改这几行就行。

## 部署到 GitHub Pages

### 一次性设置

1. 在 GitHub 创建新仓库（建议名字 `worship-sheets`），设为 **Public**（GitHub Pages 免费版只支持公开仓库）
2. 把这个文件夹的所有内容上传到仓库根目录
3. 仓库 → Settings → Pages → Source 选 `main` 分支根目录 → Save
4. 等 1-2 分钟，Pages 会给你一个 `https://<你的用户名>.github.io/worship-sheets/` 网址

### 后续更新

改完代码 → push 到 main → GitHub Pages 自动重新部署，1 分钟后生效。

## 团队成员怎么用

1. 在 iPad Safari 打开网址（建议加书签）
2. 点 Safari 底部"分享"→ "添加到主屏幕"
3. 主屏幕上就有"敬拜团歌谱"图标，像普通 App 一样打开
4. 第一次打开会自动跳本周；以后可在列表页选别的周

**周六晚上提前打开一次，把本周歌谱图片缓存好**。主日早上即使教会 Wi-Fi 不稳，所有歌谱都已经在 iPad 本地，零延迟翻页。

## 安全说明

- Dropbox App 是 **只读**（files.metadata.read + files.content.read）
- Refresh token 写在 `index.html` 里，发布到公开 GitHub 后任何人都能看到。但因为是只读、且这个文件夹本来就准备共享给团队，所以风险极低——最坏情况是有人能读你这一个歌谱文件夹（其他 Dropbox 内容他看不到）
- 如果 Dropbox 因检测到 token 在公开仓库而自动撤销了，重新走一遍 OAuth 拿新 refresh_token 即可

## 已知限制 / 未做的功能

为了第一版能快速跑起来，下面这些没做（确认过用户不需要 v1 加）：

- ❌ 蓝牙脚踏板支持
- ❌ 新成员引导教程
- ❌ 批注/涂画
- ❌ 移调（capo）显示
- ❌ 多人同步翻页

## 故障排查

| 现象 | 排查 |
|---|---|
| 打不开网页 | 网址是不是输错了？Wi-Fi 是不是断了？ |
| 列表是空的 | Dropbox 那边文件夹被改名了？路径是不是变了？|
| 图片转圈不出来 | 第一次需要联网下载，请耐心 1-2 秒 |
| 翻页卡顿 | iPad Air 2 内存只有 2GB，应用已限制最多内存里 5 张图。退出重开会清干净缓存。|
| 想强制刷新 | 点右上角 ↻ 按钮 |

## 架构要点

- **认证**：PKCE 公共客户端流程，App key + refresh_token 配对，无需 App secret
- **API 调用**：所有请求带 `Dropbox-API-Path-Root` header 切到团队命名空间
- **缓存策略**：
  - App 静态文件（HTML/JS/CSS）→ Service Worker 网络优先 + 缓存兜底
  - 歌谱图片字节 → IndexedDB，按 Dropbox 文件 rev 索引（rev 不变就直接命中缓存）
  - 文件夹列表 → IndexedDB，30 分钟 TTL
  - Access token → sessionStorage，~3.5 小时 TTL（自动 refresh）
- **路由**：hash-based（`#/` 或 `#/w/{folder}`），无后端
- **iPad Air 2 优化**：
  - `<meta name="apple-mobile-web-app-capable">` 配合主屏幕模式
  - `-webkit-touch-callout: none` 关掉长按保存图片菜单
  - 图片预加载只缓存当前 ±2 张到内存，更远的释放 ObjectURL

## 凭据备份

完整凭据见 `dropbox-credentials.json`（**别提交到公开仓库**——这个文件不在 worship-app/ 目录里就是为了避免误传）。
