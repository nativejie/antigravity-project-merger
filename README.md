# Antigravity Project Merger

[English](./README.en.md) | 简体中文

Antigravity Project Merger 是一个本地数据清理工具，用于合并 Antigravity / Gemini 中重复生成的项目记录，并把历史对话重新迁移到正确的项目下。

> 非官方工具。请在执行迁移前先备份数据，并确认你理解它会修改本地 `.gemini` 目录下的配置文件。

## 背景

在使用 Antigravity 的过程中，同一个本地工程有时会被识别成多个项目。

这会导致：

- 项目列表中出现多个重复项目
- 历史对话分散在不同项目下
- 部分旧对话显示为 `outside-of-project`
- 项目配置和权限记录变得混乱

本工具会根据项目绑定的本地工程路径识别重复项目，保留一个主项目，并将重复项目的配置、权限和历史对话关系归并到主项目中。

## 功能特性

- 按本地工程路径识别重复项目
- 自动选择需要保留的主项目
- 合并项目 `settings`
- 合并项目 `permissionGrants`
- 迁移历史对话中的项目引用
- 自动处理部分 `outside-of-project` 老历史对话
- 正式迁移前自动创建物理备份
- 支持从备份一键恢复
- 支持 `--dry-run` 预览模式
- 支持 `--force` 非交互执行

## 适用场景

如果你遇到以下情况，可以使用本工具：

- Antigravity 中同一个代码仓库出现多个项目
- 项目列表越来越乱
- 历史对话没有归属到正确项目
- 老对话显示为 `outside-of-project`
- 想清理 `.gemini/config/projects` 中重复生成的项目配置
- 想把项目配置和历史对话重新整理到一个主项目下

## 工作原理

工具主要处理本地两个位置的数据：

```txt
~/.gemini/config/projects
~/.gemini/antigravity/agyhub_summaries_proto.pb
```

其中：

- `~/.gemini/config/projects` 保存项目 JSON 配置
- `agyhub_summaries_proto.pb` 保存对话摘要和项目关系数据

迁移流程如下：

1. 扫描所有项目 JSON 配置
2. 提取每个项目绑定的本地工程路径
3. 按工程路径对项目进行分组
4. 从每组重复项目中选择一个主项目
5. 合并重复项目中的配置和权限
6. 修改对话数据库中的项目引用
7. 删除多余的重复项目配置
8. 保留备份，方便回滚

## 环境要求

```txt
Python 3.8+
```

无需安装第三方依赖，脚本只使用 Python 标准库。

## 安装

```bash
git clone https://github.com/your-name/antigravity-project-merger.git
cd antigravity-project-merger
```

## 使用方法

### 1. 预览迁移结果

正式执行前，建议先使用 `--dry-run` 查看会被合并的项目。

```bash
python3 merge_all_in_one.py migrate --dry-run
```

该命令不会修改任何文件，只会输出待合并的项目分组、主项目和重复项目。

### 2. 创建备份

```bash
python3 merge_all_in_one.py backup
```

备份内容包括：

```txt
~/.gemini/config/projects
~/.gemini/antigravity/agyhub_summaries_proto.pb
```

备份位置：

```txt
~/.gemini/config/projects.backup
~/.gemini/antigravity/agyhub_summaries_proto.pb.migration_backup
```

### 3. 执行迁移

```bash
python3 merge_all_in_one.py migrate
```

执行后，工具会：

1. 创建备份
2. 分析重复项目
3. 展示合并计划
4. 等待用户确认
5. 修改项目配置
6. 迁移对话关系
7. 删除重复项目 JSON

### 4. 跳过交互确认

如果已经确认 `dry-run` 输出无误，可以使用：

```bash
python3 merge_all_in_one.py migrate --force
```

### 5. 从备份恢复

如果迁移结果不符合预期，可以执行：

```bash
python3 merge_all_in_one.py restore
```

该命令会把备份数据恢复到原始位置。

## 命令说明

```bash
python3 merge_all_in_one.py [backup | migrate | restore] [--dry-run] [--force]
```

| 命令 | 说明 |
|---|---|
| `backup` | 单独创建项目配置和对话数据库备份 |
| `migrate` | 执行重复项目合并和对话关系迁移 |
| `restore` | 从备份恢复原始数据 |

| 参数 | 说明 |
|---|---|
| `--dry-run` | 仅预览，不修改任何文件 |
| `--force` | 跳过交互确认，直接执行迁移 |

## 推荐流程

```bash
python3 merge_all_in_one.py migrate --dry-run
python3 merge_all_in_one.py backup
python3 merge_all_in_one.py migrate
```

如果结果异常：

```bash
python3 merge_all_in_one.py restore
```

## 项目结构

```txt
antigravity-project-merger/
├── merge_all_in_one.py
├── README.md
├── README.en.md
└── LICENSE
```

## 注意事项

- 执行前建议关闭 Antigravity 客户端
- 正式迁移前一定先执行 `--dry-run`
- 脚本会修改本地 `.gemini` 目录下的数据
- 虽然迁移前会自动备份，但仍建议你额外备份重要数据
- 本工具不是 Antigravity 官方工具，请谨慎使用

## 免责声明

本项目与 Antigravity、Google、Gemini 官方无关。

使用本工具产生的任何风险由使用者自行承担。

## License

MIT
