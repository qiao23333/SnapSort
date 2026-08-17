#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""规则引擎：分类完成后自动执行 IF-THEN 规则"""
import os
import re
import shutil
from pathlib import Path


class RuleCondition:
    """规则条件"""
    def __init__(self, condition_dict):
        self.condition = condition_dict

    def evaluate(self, file_path, category, description, confidence):
        """评估条件是否满足"""
        # 支持 AND 组合（当前版本只支持 AND，OR 后续扩展）
        cond = self.condition
        fname = os.path.basename(file_path)
        ext = os.path.splitext(fname)[1].lower()

        # category == "X"
        if "category" in cond:
            if category != cond["category"]:
                return False

        # text_contains "X" (在 AI 描述中搜索)
        if "text_contains" in cond:
            kw = cond["text_contains"].lower()
            if kw not in description.lower():
                return False

        # filename_contains "X"
        if "filename_contains" in cond:
            kw = cond["filename_contains"].lower()
            if kw not in fname.lower():
                return False

        # file_ext == ".png" 等
        if "file_ext" in cond:
            if ext != cond["file_ext"].lower():
                return False

        # confidence < N
        if "confidence_lt" in cond:
            if confidence >= cond["confidence_lt"]:
                return False

        # confidence > N
        if "confidence_gt" in cond:
            if confidence <= cond["confidence_gt"]:
                return False

        # regex_match 正则匹配文件名
        if "regex_match" in cond:
            try:
                if not re.search(cond["regex_match"], fname):
                    return False
            except re.error:
                return False

        # description_regex 正则匹配 AI 描述
        if "description_regex" in cond:
            try:
                if not re.search(cond["description_regex"], description):
                    return False
            except re.error:
                return False

        return True


class RuleAction:
    """规则动作"""
    def __init__(self, action_dict):
        self.action = action_dict

    def execute(self, file_path, output_base):
        """执行动作，返回 (success, message, new_path_or_none)"""
        action = self.action
        action_type = action.get("type", "move")

        if action_type == "move":
            return self._action_move(file_path, output_base, action)
        elif action_type == "rename":
            return self._action_rename(file_path, action)
        elif action_type == "copy":
            return self._action_copy(file_path, output_base, action)
        elif action_type == "add_tag":
            # 标签目前只是在日志中体现，后续可扩展到元数据
            return True, f"添加标签: {action.get('tag', '')}", file_path
        else:
            return False, f"未知动作类型: {action_type}", None

    def _action_move(self, file_path, output_base, action):
        """移动文件到目标子目录"""
        target_subdir = action.get("target_dir", "")
        if not target_subdir:
            return False, "未指定目标目录", None

        # 支持变量替换: {category} -> 分类目录名
        target_subdir = target_subdir.replace("{category}", os.path.basename(os.path.dirname(file_path)))

        dest_dir = os.path.join(output_base, target_subdir)
        os.makedirs(dest_dir, exist_ok=True)

        fname = os.path.basename(file_path)
        dest_path = os.path.join(dest_dir, fname)

        # 处理重名
        if os.path.exists(dest_path):
            base, ext = os.path.splitext(dest_path)
            i = 1
            while os.path.exists(f"{base}_{i:03d}{ext}"):
                i += 1
            dest_path = f"{base}_{i:03d}{ext}"

        try:
            shutil.move(file_path, dest_path)
            return True, f"已移动到 {target_subdir}/{os.path.basename(dest_path)}", dest_path
        except OSError as e:
            return False, f"移动失败: {e}", None

    def _action_rename(self, file_path, action):
        """重命名文件"""
        pattern = action.get("pattern", "{name}")
        fname = os.path.basename(file_path)
        base, ext = os.path.splitext(fname)

        new_name = pattern.replace("{name}", base).replace("{ext}", ext)
        if not new_name.endswith(ext):
            new_name += ext

        new_path = os.path.join(os.path.dirname(file_path), new_name)
        if os.path.exists(new_path):
            return False, f"目标文件已存在: {new_name}", None

        try:
            os.rename(file_path, new_path)
            return True, f"已重命名为 {new_name}", new_path
        except OSError as e:
            return False, f"重命名失败: {e}", None

    def _action_copy(self, file_path, output_base, action):
        """复制文件到目标子目录"""
        target_subdir = action.get("target_dir", "")
        if not target_subdir:
            return False, "未指定目标目录", None

        dest_dir = os.path.join(output_base, target_subdir)
        os.makedirs(dest_dir, exist_ok=True)

        fname = os.path.basename(file_path)
        dest_path = os.path.join(dest_dir, fname)

        try:
            shutil.copy2(file_path, dest_path)
            return True, f"已复制到 {target_subdir}/{fname}", dest_path
        except OSError as e:
            return False, f"复制失败: {e}", None


class RuleEngine:
    """规则引擎：管理规则集合并批量执行"""

    def __init__(self, rules=None, log_callback=None):
        """
        rules: 规则列表，每个规则包含 name, condition, action
        示例:
        [
            {
                "name": "微信截图归类",
                "enabled": true,
                "condition": {"category": "截图", "text_contains": "微信"},
                "action": {"type": "move", "target_dir": "WeChat_Screenshots"}
            }
        ]
        """
        self.rules = rules or []
        self.log_callback = log_callback

    def log(self, msg, level="INFO"):
        if self.log_callback:
            self.log_callback(msg)

    def add_rule(self, name, condition, action, enabled=True):
        """添加一条规则"""
        self.rules.append({
            "name": name,
            "enabled": enabled,
            "condition": condition,
            "action": action
        })

    def remove_rule(self, name):
        """删除规则"""
        self.rules = [r for r in self.rules if r.get("name") != name]

    def get_rules(self):
        """获取所有规则"""
        return self.rules

    def apply(self, file_path, category, description, confidence, output_base):
        """
        对单个文件应用所有启用规则
        返回: [(rule_name, success, message)]
        """
        results = []
        for rule in self.rules:
            if not rule.get("enabled", True):
                continue

            try:
                cond = RuleCondition(rule["condition"])
                if cond.evaluate(file_path, category, description, confidence):
                    action = RuleAction(rule["action"])
                    success, msg, _ = action.execute(file_path, output_base)
                    results.append((rule["name"], success, msg))

                    if success and self.log_callback:
                        self.log(f"  规则「{rule['name']}」: {msg}")
                    elif not success and self.log_callback:
                        self.log(f"  规则「{rule['name']}」失败: {msg}", "WARN")
            except Exception as e:
                results.append((rule.get("name", "?"), False, str(e)))
                if self.log_callback:
                    self.log(f"  规则执行异常: {e}", "ERROR")

        return results

    def apply_all(self, results_dict, output_base):
        """
        对分类结果批量应用规则
        results_dict: {category: [(file_path, description), ...]}
        返回: 统计信息
        """
        total_rules = 0
        total_matches = 0
        total_actions = 0

        enabled_rules = [r for r in self.rules if r.get("enabled", True)]
        if not enabled_rules:
            if self.log_callback:
                self.log("没有启用的规则，跳过规则引擎", "INFO")
            return {"rules_checked": 0, "matches": 0, "actions": 0}

        if self.log_callback:
            self.log(f"开始执行 {len(enabled_rules)} 条规则...", "INFO")

        for category, files in results_dict.items():
            for file_path, description in files:
                if not os.path.exists(file_path):
                    continue
                results = self.apply(
                    file_path, category, description,
                    confidence=0.7, output_base=output_base
                )
                for rname, success, msg in results:
                    total_rules += 1
                    if success:
                        total_actions += 1

        if self.log_callback:
            self.log(f"规则引擎完成：检查 {total_rules} 次，执行 {total_actions} 次操作", "OK")

        return {
            "rules_checked": total_rules,
            "matches": total_rules,
            "actions": total_actions
        }


# 预设规则模板（供用户参考修改）
PRESET_RULES = [
    {
        "name": "低置信度文件归档",
        "enabled": False,
        "condition": {"category": "待复核"},
        "action": {"type": "move", "target_dir": "未分类"}
    },
    {
        "name": "截图归类",
        "enabled": False,
        "condition": {"text_contains": "截图"},
        "action": {"type": "move", "target_dir": "截图"}
    },
    {
        "name": "大尺寸图片另存",
        "enabled": False,
        "condition": {"category": "澳洲风景图"},
        "action": {"type": "copy", "target_dir": "精选澳洲风景"}
    }
]
