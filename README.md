# BiliPink 安卓项目

这是一个面向 Android 的 Python + Kivy 项目，界面参考提供的两张截图：白色背景、浅粉色强调色、圆角任务卡片、顶部 BV/AV 搜索、任务筛选、底部「主页 / 我的」导航，以及「代码仓库 / 当前版本 / 开源组件许可 / 问题反馈 / 设置 / 给我们评分 / 已下载文件 / 清除数据」页面。

## 功能

- 识别 BV、AV、Bilibili 完整链接和 b23 短链接。
- 通过 B 站公开接口获取标题、UP 主、时长、封面和互动数据。
- 查询接口实际返回的可用直连 MP4 画质，不虚构画质。
- 后台线程下载，展示真实字节进度；失败时显示错误信息并清理不完整文件。
- 下载历史以 UTF-8 JSON 保存，标题与文件名保留中文。
- 已下载文件可尝试通过 Android MediaStore 导出到 `Download/BiliPink`。
- GitHub Actions 自动下载 Noto Sans CJK 简体中文字体并打包，降低中文缺字/乱码风险。

## GitHub Actions 云端编译

1. 将本目录中的所有文件上传到 GitHub 仓库根目录，必须保留 `.github/workflows/build-apk.yml`。
2. 打开仓库的 **Actions** 页面，运行 **Build BiliPink APK**，或推送到 `main` / `master` 分支。
3. 成功后进入本次 workflow run 页面，在 **Artifacts** 下载 `BiliPink-debug-apk`，解压得到 APK。
4. 在 Android 手机上安装测试。首次安装时，系统可能提示允许安装未知来源应用。

## 重要限制

- 本项目源码和工作流已准备，但需要真实的 GitHub Actions 构建和安卓设备测试才能确认 APK 可安装运行。
- 当前下载实现只接受 B 站接口返回的直连视频流。部分视频仅提供 DASH 分离音视频，当前版本会明确提示不支持，不会把错误网页保存成 MP4；DASH 音视频合并尚未实现。
- 登录和 Cookie 登录 UI 未实现；受账号权限限制的画质可能无法获取。
- 导出依赖 Android MediaStore；如系统拒绝写入，原文件仍保留在应用私有目录。
- 字体由 workflow 下载自 Noto CJK 项目，并随 APK 打包；字体许可文件也会一起打包。

## 文件

- `main.py`：界面、任务状态、历史、导出和设置
- `bili_api.py`：B 站视频链接解析与公开 API
- `downloader.py`：下载、文件名和下载内容检查
- `buildozer.spec`：Android 打包配置
- `.github/workflows/build-apk.yml`：GitHub Actions 构建工作流
- `assets/avatar-reference.jpg`：参考截图中的头像裁剪图
