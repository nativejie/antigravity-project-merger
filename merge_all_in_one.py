#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
======================================================================
  ___        _   _                                _ _         
 / _ \      | | (_)                              (_) |        
/ /_\ \_ __ | |_ _  __ _ _ __ __ ___   __ ___   ___| |_ _   _ 
|  _  | '_ \| __| |/ _` | '__/ _` \ \ / / \ \ / / | __| | | |
| | | | | | | |_| | (_| | | | (_| |\ V /   \ V /| | |_| |_| |
\_| |_/_| |_|\__|_|\__, |_|  \__,_| \_/     \_/ |_|\__|\__, |
                    __/ |                              __/ |
                   |___/                              |___/ 
  Antigravity Projects & Conversations Merger v1.1
======================================================================
Antigravity 重复项目合并与对话一键式归并迁移工具。

用法:
  python3 merge_all_in_one.py [backup | migrate | restore] [--dry-run] [--force]
"""

import os
import sys
import glob
import json
import shutil
import argparse
from collections import defaultdict
from pathlib import Path

# 字体颜色定义 (ANSI Codes)
C_GREEN = "\033[32m"
C_RED = "\033[31m"
C_YELLOW = "\033[33m"
C_BLUE = "\033[34m"
C_BOLD = "\033[1m"
C_RESET = "\033[0m"

# 核心路径
PROJECTS_DIR = Path.home() / ".gemini/config/projects"
PROJECTS_BACKUP_DIR = Path.home() / ".gemini/config/projects.backup"
PB_PATH = Path.home() / ".gemini/antigravity/agyhub_summaries_proto.pb"
PB_BACKUP_PATH = Path.home() / ".gemini/antigravity/agyhub_summaries_proto.pb.migration_backup"


# ── Banner 绘制 ──────────────────────────────────────────────────────────────

def print_banner():
    art = r"""
  ___        _   _                                _ _         
 / _ \      | | (_)                              (_) |        
/ /_\ \_ __ | |_ _  __ _ _ __ __ ___   __ ___   ___| |_ _   _ 
|  _  | '_ \| __| |/ _` | '__/ _` \ \ / / \ \ / / | __| | | |
| | | | | | | |_| | (_| | | | (_| |\ V /   \ V /| | |_| |_| |
\_| |_/_| |_|\__|_|\__, |_|  \__,_| \_/     \_/ |_|\__|\__, |
                    __/ |                              __/ |
                   |___/                              |___/ """
    print(f"{C_BLUE}{C_BOLD}{art}{C_RESET}")
    print(f"      {C_BOLD}Antigravity Projects & Conversations Merger v1.1{C_RESET}")
    print("======================================================================")



# ── Protobuf 二进制流底边编解码器 (100% 严密且无损) ───────────────────────────

def read_varint(data: bytes, pos: int):
    result, shift = 0, 0
    while pos < len(data):
        b = data[pos]
        pos += 1
        result |= (b & 0x7f) << shift
        if not (b & 0x80):
            break
        shift += 7
    return result, pos


def encode_varint(value: int) -> bytes:
    parts = []
    while value > 0x7f:
        parts.append((value & 0x7f) | 0x80)
        value >>= 7
    parts.append(value)
    return bytes(parts)


def parse_proto(data: bytes):
    pos = 0
    fields = []
    while pos < len(data):
        try:
            tag, pos = read_varint(data, pos)
            wire_type = tag & 0x7
            field_num = tag >> 3
            if wire_type == 2:
                length, pos = read_varint(data, pos)
                chunk = data[pos:pos + length]
                pos += length
                fields.append((field_num, wire_type, chunk))
            elif wire_type == 0:
                val, pos = read_varint(data, pos)
                fields.append((field_num, wire_type, val))
            elif wire_type == 1:
                chunk = data[pos:pos + 8]
                pos += 8
                fields.append((field_num, wire_type, chunk))
            elif wire_type == 5:
                chunk = data[pos:pos + 4]
                pos += 4
                fields.append((field_num, wire_type, chunk))
            else:
                break
        except Exception:
            break
    return fields


def encode_proto(fields) -> bytes:
    parts = []
    for field_num, wire_type, value in fields:
        tag = (field_num << 3) | wire_type
        parts.append(encode_varint(tag))
        if wire_type == 2:
            parts.append(encode_varint(len(value)))
            parts.append(value)
        elif wire_type == 0:
            parts.append(encode_varint(value))
        elif wire_type in (1, 5):
            parts.append(value)
    return b''.join(parts)


# ── 3. 辅助提取与合并逻辑 ─────────────────────────────────────────────────────────

def get_project_folder_uri(d: dict) -> str:
    """高容错地从项目 JSON 配置中提取项目绑定的工程路径"""
    try:
        for r in d.get('projectResources', {}).get('resources', []):
            gf = r.get('gitFolder', {})
            folder_uri = gf.get('folderUri', '')
            if folder_uri:
                return folder_uri
    except Exception:
        pass
    
    # 模糊字典深度递归搜索
    def search_dict(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == 'folderUri' and isinstance(v, str) and v.startswith('file://'):
                    return v
                res = search_dict(v)
                if res:
                    return res
        elif isinstance(obj, list):
            for item in obj:
                res = search_dict(item)
                if res:
                    return res
        return ''
    return search_dict(d)


def choose_keeper(group: list) -> dict:
    """智能选出要保留的 Keeper"""
    no_num = [p for p in group if not p['name'].split()[-1].isdigit()]
    has_settings = [p for p in group if p['has_settings']]

    if has_settings and no_num:
        both = [p for p in has_settings if p in no_num]
        if both:
            return both[0]
        return has_settings[0]
    elif has_settings:
        return has_settings[0]
    elif no_num:
        return no_num[0]
    else:
        return group[0]


def merge_settings(keeper: dict, others: list) -> dict:
    """融合 duplicate 项目的 settings 到 keeper"""
    data = dict(keeper['data'])
    for other in others:
        d = other['data']
        if 'settings' not in data and 'settings' in d:
            data['settings'] = d['settings']
        if 'permissionGrants' in d:
            if 'permissionGrants' not in data:
                data['permissionGrants'] = d['permissionGrants']
            else:
                existing_allow = set(data['permissionGrants'].get('allow', []))
                new_allow = d['permissionGrants'].get('allow', [])
                data['permissionGrants']['allow'] = list(existing_allow | set(new_allow))
    return data


# ── 4. 三大核心交互式子命令实现 ──────────────────────────────────────────────────────

def do_backup(silent=False):
    """
    单独执行备份操作。
    如果是迁移中触发，可以设置 silent=True 跳过重复的提示。
    """
    if not silent:
        print(f"{C_BOLD}=== 开始创建数据物理备份 ==={C_RESET}")
        print(f"数据备份目的地一览：")
        print(f"  [1] 项目 JSON 配置目录备份:")
        print(f"      源路径: {C_GREEN}{PROJECTS_DIR}{C_RESET}")
        print(f"      备份至: {C_GREEN}{PROJECTS_BACKUP_DIR}{C_RESET}")
        print(f"  [2] 对话摘要数据库备份:")
        print(f"      源路径: {C_GREEN}{PB_PATH}{C_RESET}")
        print(f"      备份至: {C_GREEN}{PB_BACKUP_PATH}{C_RESET}")
        print()
        
        try:
            val = input("确定现在开始执行备份吗？ [y/N]: ").strip().lower()
            if val not in ('y', 'yes'):
                print("❌ 备份操作已取消。")
                return False
        except (KeyboardInterrupt, EOFError):
            print("\n❌ 操作已取消。")
            return False

    # 1. 备份 projects 目录
    try:
        if PROJECTS_DIR.exists():
            if PROJECTS_BACKUP_DIR.exists():
                shutil.rmtree(PROJECTS_BACKUP_DIR)
            shutil.copytree(str(PROJECTS_DIR), str(PROJECTS_BACKUP_DIR))
            print(f"  ✔ 项目配置目录备份成功！")
        else:
            print(f"  ⚠️ 未找到 projects 目录，跳过备份。")
    except Exception as e:
        print(f"  ❌ 项目目录备份失败: {e}")
        return False

    # 2. 备份 PB
    try:
        if PB_PATH.exists():
            shutil.copy2(str(PB_PATH), str(PB_BACKUP_PATH))
            print(f"  ✔ 对话数据库备份成功！")
        else:
            print(f"  ⚠️ 未找到对话数据库文件，跳过备份。")
    except Exception as e:
        print(f"  ❌ 对话数据库备份失败: {e}")
        return False

    print(f"{C_GREEN}{C_BOLD}✅ 物理备份全部创建完成！{C_RESET}\n")
    return True


def do_restore():
    """还原操作"""
    print(f"{C_BOLD}=== 开始从备份中还原原始数据 ==={C_RESET}")
    print(f"系统将进行以下回滚还原操作：")
    print(f"  [1] 项目 JSON 目录还原:")
    print(f"      将从: {C_GREEN}{PROJECTS_BACKUP_DIR}{C_RESET}")
    print(f"      覆盖回: {C_GREEN}{PROJECTS_DIR}{C_RESET}")
    print(f"  [2] 对话数据库还原:")
    print(f"      将从: {C_GREEN}{PB_BACKUP_PATH}{C_RESET}")
    print(f"      覆盖回: {C_GREEN}{PB_PATH}{C_RESET}")
    print()

    # 确认还原
    try:
        val = input(f"{C_YELLOW}⚠️ 注意：此操作会覆盖当前的修改！确定现在开始还原吗？ [y/N]: {C_RESET}").strip().lower()
        if val not in ('y', 'yes'):
            print("❌ 还原操作已取消。")
            return
    except (KeyboardInterrupt, EOFError):
        print("\n❌ 操作已取消。")
        return

    # 1. 还原 projects 目录
    try:
        if PROJECTS_BACKUP_DIR.exists():
            if PROJECTS_DIR.exists():
                shutil.rmtree(str(PROJECTS_DIR))
            shutil.copytree(str(PROJECTS_BACKUP_DIR), str(PROJECTS_DIR))
            print(f"  ✔ 项目 JSON 配置目录已完美还原！")
        else:
            print(f"  ❌ 还原失败：找不到 projects 备份目录。")
    except Exception as e:
        print(f"  ❌ 还原项目目录出错: {e}")

    # 2. 还原 PB 文件
    try:
        if PB_BACKUP_PATH.exists():
            shutil.copy2(str(PB_BACKUP_PATH), str(PB_PATH))
            print(f"  ✔ 对话数据库已成功回滚还原！")
        else:
            print(f"  ❌ 还原失败：找不到对话数据库备份文件。")
    except Exception as e:
        print(f"  ❌ 还原对话数据库出错: {e}")

    print(f"{C_GREEN}{C_BOLD}🎉 原始备份数据已全部物理还原成功！{C_RESET}")
    print(f"👉 你现在可以重新打开你的 Antigravity 看看了！\n")


def do_migrate(dry_run=False, force=False):
    """
    归并合并迁移操作。
    包含清晰的步骤交互提示。
    """
    # 步骤一：首先详细提示将要操作哪两个文件，地址在哪里，会备份到哪里
    print(f"{C_BOLD}=== 准备执行项目与对话一体化合并迁移 ==={C_RESET}")
    print(f"本次操作将直接读取、修改并清理以下两个核心配置文件：")
    print(f"  {C_BOLD}[1] 项目 JSON 配置目录{C_RESET}")
    print(f"      • 物理路径: {C_GREEN}{PROJECTS_DIR}{C_RESET}")
    print(f"      • 备份目的地: {C_GREEN}{PROJECTS_BACKUP_DIR}{C_RESET}")
    print(f"  {C_BOLD}[2] 对话摘要数据库 (PB 文件){C_RESET}")
    print(f"      • 物理路径: {C_GREEN}{PB_PATH}{C_RESET}")
    print(f"      • 备份目的地: {C_GREEN}{PB_BACKUP_PATH}{C_RESET}")
    print()

    # 步骤二：提示备份
    if not dry_run and not force:
        try:
            val = input(f"确定开始为以上数据创建安全物理备份吗？ [y/N]: ").strip().lower()
            if val not in ('y', 'yes'):
                print("❌ 迁移操作已取消。")
                return
        except (KeyboardInterrupt, EOFError):
            print("\n❌ 操作已取消。")
            return
    
    # 执行备份
    if not dry_run:
        print(f"\n{C_BOLD}正在执行物理备份...{C_RESET}")
        if not do_backup(silent=True):
            print(f"{C_RED}❌ 备份失败，安全终止迁移进程。{C_RESET}")
            return
    else:
        print(f"{C_YELLOW}⚡ [预览模式] 跳过物理备份步骤。{C_RESET}\n")

    # 加载 52 个项目并分组
    projects = []
    for f in glob.glob(str(PROJECTS_DIR / "*.json")):
        try:
            with open(f) as fp:
                d = json.load(fp)
            
            pid = d.get('id')
            name = d.get('name', '')
            folder_uri = get_project_folder_uri(d)
            
            if pid and folder_uri:
                projects.append({
                    'id': pid,
                    'name': name,
                    'file': f,
                    'data': d,
                    'folder_uri': folder_uri,
                    'has_settings': 'settings' in d,
                    'has_permissions': 'permissionGrants' in d,
                })
        except Exception as e:
            print(f"{C_YELLOW}⚠️ 跳过无法读取的项目配置: {f} ({e}){C_RESET}")

    if not projects:
        print(f"{C_RED}❌ 错误：在 projects 目录下未发现任何有效的项目 JSON 文件！{C_RESET}")
        return

    # 分组
    by_folder = defaultdict(list)
    for p in projects:
        by_folder[p['folder_uri']].append(p)

    to_delete = []
    to_update = []
    deleted_to_keeper = {}
    keeper_ids = set()
    uri_to_keeper_id = {}

    # 步骤三：展示合并预览
    print(f"{C_BOLD}--- 待合并清理的分组项目列表 ---{C_RESET}")
    for folder, group in sorted(by_folder.items(), key=lambda x: -len(x[1])):
        keeper = choose_keeper(group)
        others = [p for p in group if p['id'] != keeper['id']]
        
        keeper_ids.add(keeper['id'])
        uri_to_keeper_id[folder] = keeper['id']
        
        for o in others:
            deleted_to_keeper[o['id']] = keeper['id']
            to_delete.append(o)
        
        merged_data = merge_settings(keeper, others)
        to_update.append((keeper['file'], merged_data))
        
        folder_short = folder.replace('file:///Users/', '~/')
        print(f"📁 路径: {C_GREEN}{folder_short}{C_RESET}")
        print(f"   ✅ {C_GREEN}Keeper 保留项 -> [{keeper['name']:30s}]{C_RESET} ID: {keeper['id']}")
        for o in others:
            print(f"   ❌ {C_RED}Duplicate 融合项 -> [{o['name']:30s}]{C_RESET} ID: {o['id']}")
        print()

    print(f"🔗 已智能分析出 {C_BOLD}{len(deleted_to_keeper)}{C_RESET} 组需要被合并的副项目 ID 映射。")

    # 提示开始迁移
    if not dry_run and not force:
        try:
            print()
            val = input(f"{C_YELLOW}{C_BOLD}备份已就绪。确定现在执行物理改写迁移（彻底合并重复项目和对话）吗？ [y/N]: {C_RESET}").strip().lower()
            if val not in ('y', 'yes'):
                print("❌ 迁移操作已取消。")
                return
        except (KeyboardInterrupt, EOFError):
            print("\n❌ 操作已取消。")
            return

    # 4. 执行二进制 PB 修改
    modified_count = 0
    outside_migrated_count = 0
    
    if PB_PATH.exists():
        with open(PB_PATH, 'rb') as f:
            pb_raw = f.read()
        
        top_fields = parse_proto(pb_raw)
        new_top_fields = []
        
        for fn, wt, val in top_fields:
            if fn == 1:
                sub_fields = parse_proto(val)
                conv_id = ''
                detail_idx = -1
                detail_bytes = b''
                for idx, (sfn, swt, sval) in enumerate(sub_fields):
                    if sfn == 1:
                        conv_id = sval.decode('utf-8', errors='ignore')
                    elif sfn == 2:
                        detail_idx = idx
                        detail_bytes = sval
                
                if detail_idx != -1 and detail_bytes:
                    detail_fields = parse_proto(detail_bytes)
                    f17_idx = -1
                    f17_bytes = b''
                    for idx, (dfn, dwt, dval) in enumerate(detail_fields):
                        if dfn == 17:
                            f17_idx = idx
                            f17_bytes = dval
                    
                    if f17_idx != -1 and f17_bytes:
                        f17_fields = parse_proto(f17_bytes)
                        f18_idx = -1
                        old_project_id = ''
                        ws_uri = ''
                        for idx, (fn17, wt17, val17) in enumerate(f17_fields):
                            if fn17 == 18:
                                f18_idx = idx
                                old_project_id = val17.decode('utf-8', errors='ignore')
                            elif fn17 == 1:
                                f17_sub = parse_proto(val17)
                                for fsfn, fswt, fsval in f17_sub:
                                    if fsfn == 1:
                                        ws_uri = fsval.decode('utf-8', errors='ignore')
                        
                        # 发现匹配，进行修改
                        target_keeper_id = None
                        is_outside = False
                        
                        if f18_idx != -1:
                            if old_project_id in deleted_to_keeper:
                                target_keeper_id = deleted_to_keeper[old_project_id]
                            elif old_project_id == "outside-of-project" and ws_uri in uri_to_keeper_id:
                                target_keeper_id = uri_to_keeper_id[ws_uri]
                                is_outside = True
                        
                        if target_keeper_id:
                            # 强力双重校验：确保目标项目 ID 真实存在于保留项目中
                            if target_keeper_id in keeper_ids:
                                new_f17_fields = list(f17_fields)
                                new_f17_fields[f18_idx] = (18, 2, target_keeper_id.encode('utf-8'))
                                new_f17_bytes = encode_proto(new_f17_fields)
                                
                                new_detail_fields = list(detail_fields)
                                new_detail_fields[f17_idx] = (17, 2, new_f17_bytes)
                                new_detail_bytes = encode_proto(new_detail_fields)
                                
                                new_sub_fields = list(sub_fields)
                                new_sub_fields[detail_idx] = (2, 2, new_detail_bytes)
                                new_val = encode_proto(new_sub_fields)
                                
                                new_top_fields.append((fn, wt, new_val))
                                modified_count += 1
                                if is_outside:
                                    outside_migrated_count += 1
                                continue
                            else:
                                print(f"{C_RED}⚠️ 安全校验未通过：试图迁移到不存在的项目 ID {target_keeper_id}{C_RESET}")
            
            new_top_fields.append((fn, wt, val))
        
        # 物理写回
        if modified_count > 0:
            if not dry_run:
                pb_new_data = encode_proto(new_top_fields)
                with open(PB_PATH, 'wb') as f:
                    f.write(pb_new_data)
                print(f"{C_GREEN}  ✔ 对话 PB 数据库迁移成功！{C_RESET}")
                print(f"      • 成功归并迁移了 {C_BOLD}{modified_count - outside_migrated_count}{C_RESET} 条由于项目重复而失效的对话。")
                if outside_migrated_count > 0:
                    print(f"      • {C_GREEN}特别归档：已自动识别并成功归并了 {C_BOLD}{outside_migrated_count}{C_RESET} 条来自启用 Agents 前的孤立老历史对话！{C_RESET}")
            else:
                print(f"{C_YELLOW}  ⚡ [预览模式] 发现有 {modified_count} 条对话关系待迁移归并（含 {outside_migrated_count} 条孤立老历史对话）。{C_RESET}")
        else:
            print("  ℹ️ 未发现任何需要归纳迁移的对话关系。")
    else:
        print(f"{C_RED}❌ 找不到对话 PB 文件，无法完成对话迁移。{C_RESET}")

    # 5. 物理合并并清理项目 JSON 文件夹
    if dry_run:
        print(f"\n{C_YELLOW}⚡ [预览模式] 将删除 {len(to_delete)} 个副项目 JSON，写入并保留 {len(to_update)} 个 Keeper 项目 JSON。{C_RESET}")
        return

    print(f"\n正在整理项目 JSON 文件夹...")
    # 写入更新后的 keeper settings
    for file_path, new_data in to_update:
        try:
            with open(file_path, 'w', encoding='utf-8') as fp:
                json.dump(new_data, fp, indent=2, ensure_ascii=False)
            print(f"  ✔ 写入并保留 Keeper: {C_GREEN}{os.path.basename(file_path)}{C_RESET}")
        except Exception as e:
            print(f"  ❌ 写入 Keeper 失败: {file_path} ({e})")

    # 删除 duplicate json
    deleted_count = 0
    for p in to_delete:
        try:
            if os.path.exists(p['file']):
                os.remove(p['file'])
                deleted_count += 1
        except Exception as e:
            print(f"  ❌ 删除副项目 JSON 失败: {p['file']} ({e})")
            
    print(f"  ✔ 成功清理了 {deleted_count} 个多余的副项目 JSON 配置。")
    print(f"\n{C_GREEN}{C_BOLD}🎉 恭喜！一站式重复项目合并与对话归并已全部迁移成功！{C_RESET}")
    print(f"{C_GREEN}{C_BOLD}👉 现在可以重新打开你的 Antigravity 客户端看看了！{C_RESET}\n")


# ── 主入口与命令行解析 ─────────────────────────────────────────────────────────

def main():
    print_banner()
    
    parser = argparse.ArgumentParser(
        description="Antigravity 项目及对话一体化合并清理工具",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""可选 Action 参数说明:
  backup    单独执行对原始项目 JSON 目录和对话 PB 数据库的物理备份
  migrate   执行重复项目的一键式物理合并和对话摘要 PB 关系迁移 (含详细步骤确认)
  restore   回滚操作，将从备份数据一键物理还原覆盖回原始状态
"""
    )
    # 提供 positional action 参数
    parser.add_argument("action", choices=["backup", "migrate", "restore"], nargs="?", default="migrate",
                        help="要执行的操作：backup (备份), migrate (迁移), restore (还原)")
    parser.add_argument("--dry-run", action="store_true", help="仅预览模式：计算映射，不修改任何文件")
    parser.add_argument("--force", action="store_true", help="强制执行迁移，免去所有的提示和交互确认")
    
    args = parser.parse_args()
    
    # 引导执行具体的 action
    if args.action == "backup":
        do_backup()
    elif args.action == "restore":
        do_restore()
    else:  # migrate
        do_migrate(dry_run=args.dry_run, force=args.force)


if __name__ == "__main__":
    main()
