# 映记 · 素材回顾与整理

Windows素材回顾工具：浏览素材时录下讲解，整理语音与画面证据，形成可交给AI创作和剪辑的完整资料。

## 下载应用

- [国内下载：Gitee发行版](https://gitee.com/zhanglinleo1-maker/yingji-releases/releases)：在对应版本中下载附件；ZIP请先解压，再运行安装程序。只有附件实际上传并校验成功的版本才是可用国内版本；仓库页面同步不代表附件已发布。
- [GitHub下载：beta8安装包与版本说明](https://github.com/zhanglinleo1-maker/yingji-releases/releases/tag/v0.2.0-beta8)
- [GitHub全部版本](https://github.com/zhanglinleo1-maker/yingji-releases/releases)

适用于Windows 10/11 64位。免费公开测试，未作商业代码签名。安装前关闭旧应用，不要安装到开发项目目录；对照Release的SHA256核对文件。升级后的数据保留和真实环境兼容仍需实测，重要资料建议自行备份。

## 配套开源Skill与详细规则

- [国内Skill仓库与下载](https://gitee.com/zhanglinleo1-maker/review-to-edit)：在仓库中选择“克隆/下载 → 下载ZIP”，不需要跳转GitHub；镜像版本以实际内容为准。
- [国内完整AI粗剪执行详细规则](https://gitee.com/zhanglinleo1-maker/review-to-edit/blob/main/docs/AI粗剪执行详细规则.md)
- [GitHub Skill仓库](https://github.com/zhanglinleo1-maker/review-to-edit)
- [GitHub Skill整理下载包](https://github.com/zhanglinleo1-maker/review-to-edit/releases)

应用负责回顾与证据整理，Skill指导Agent检查资料、确认需求、写脚本、制作粗剪和交付可编辑工程。Skill采用MIT许可，允许按许可修改与分发；这不将映记应用、LOGO或第三方组件一并授予MIT许可。应用本体免费使用，但未作为完整开源项目发布；包内Python代码可读。本仓库不含整个应用源码项目、私人历史或用户数据。


beta8已将应用内Skill按钮修正为公开GitHub与Gitee地址，无需私有项目权限。beta7旧按钮问题仍保留在历史包中，请升级或使用本页公开链接。

## 云端服务与统计

云端识别需要自行配置服务密钥，调用可能收费；仅按用户启用配置提交录音、图片或文本。首次启用统计向飞书发送应用版本、Windows平台、随机安装编号和首次启用日期；不主动发送素材、录音、转写、文件名或路径。网络请求由接收服务处理，不承诺完全匿名。客户端统计配置可被提取，发行者已知悉该风险。

## 版本状态与许可边界

当前为公开测试版。规则、自动测试、实际安装和用户验收分别记录，不保证所有机器和剪辑软件版本兼容。第三方组件适用各自许可证，完整分发核查及配套材料仍未完成；本仓库不宣称已取得全面合规认证。免费分发不替代第三方许可义务。

更新检查读取version.json。Gitee自动发布流程需要维护者首次配置授权；附件上传并匿名下载校验成功后才补上国内更新入口，失败不会把未完成版本标为可下载。反馈问题请说明应用版本、出错步骤及脱敏截图，不提交API Key、统计接收地址或私人素材。
