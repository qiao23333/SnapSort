#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
事件分类引擎 — 按日期分组、AI事件命名、ABC故事性分级、批量重命名、断点续传。

v3.0 重写：Checkpoint / Analyzer / Renamer 各自独立，Pipeline 串联。
"""
import os
import json
import re
import shutil
from datetime import datetime
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from .image_utils import is_image_file, encode_image, _safe_open_image, _cleanup_temp

OLLAMA = "http://localhost:11434"


# ═══════════════════════════════════════════
#  Checkpoint — 断点续传
# ═══════════════════════════════════════════

class Checkpoint:
    """管理 .checkpoint.json，记录已处理的事件日期。"""

    @staticmethod
    def path(output_dir):
        return os.path.join(output_dir, ".snapsort_checkpoint.json")

    @staticmethod
    def load(output_dir):
        p = Checkpoint.path(output_dir)
        if not os.path.exists(p):
            return set()
        try:
            with open(p, "r") as f:
                return set(json.load(f).get("dates", []))
        except Exception:
            return set()

    @staticmethod
    def save(output_dir, dates):
        p = Checkpoint.path(output_dir)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        try:
            with open(p, "w") as f:
                json.dump({"dates": sorted(dates)}, f, ensure_ascii=False)
        except Exception:
            pass

    @staticmethod
    def clear(output_dir):
        try:
            os.remove(Checkpoint.path(output_dir))
        except Exception:
            pass

    @staticmethod
    def is_done(output_dir, date):
        return date in Checkpoint.load(output_dir)


# ═══════════════════════════════════════════
#  照片扫描 & 日期分组
# ═══════════════════════════════════════════

def scan_photos(directory):
    """递归扫描目录中的图片，返回路径列表。"""
    photos = []
    for root, _, files in os.walk(directory):
        for f in files:
            path = os.path.join(root, f)
            if is_image_file(path):
                photos.append(path)
    return photos


def get_datetime(image_path):
    """从 EXIF 或文件修改时间获取完整 datetime 对象。"""
    opened = None
    try:
        img, opened = _safe_open_image(image_path)
        exif = img.getexif()
        if exif:
            for tag in (36867, 36868, 306):
                s = exif.get(tag)
                if s:
                    try:
                        return datetime.strptime(s.strip(), "%Y:%m:%d %H:%M:%S")
                    except ValueError:
                        pass
    except Exception:
        pass
    finally:
        _cleanup_temp(opened, image_path)
    try:
        return datetime.fromtimestamp(os.path.getmtime(image_path))
    except Exception:
        return None


def get_date(image_path):
    """从 EXIF 或文件修改时间获取 'YYYY-MM-DD'。"""
    dt = get_datetime(image_path)
    if dt:
        return dt.strftime("%Y-%m-%d")
    return "unknown"


def is_screenshot(image_path):
    """检测是否为截图/转发图片（无 EXIF + 文件名特征）。"""
    # 1. 有 EXIF 的大概率是真实照片
    opened = None
    try:
        img, opened = _safe_open_image(image_path)
        exif = img.getexif()
        if exif and len(exif) > 2:
            return False
    except Exception:
        pass
    finally:
        _cleanup_temp(opened, image_path)

    # 2. 无 EXIF，检查文件名特征
    name = os.path.basename(image_path).upper()
    patterns = [
        r'IMG_\d+\.PNG$',          # iPhone 截图
        r'SCREENSHOT[_-]\d+',      # Android 截图
        r'MMEXPORT\w+',            # 微信导出
        r'IMAGE[_-]\d+',           # 通用转发图
        r'IMG_\d+\.(JPG|JPEG)$',  # 无 EXIF 的 JPG（可能转发）
    ]
    return any(re.match(p, name) for p in patterns)


def group_by_date(photos):
    """{date: [path, ...]}，按日期升序。"""
    g = defaultdict(list)
    for p in photos:
        g[get_date(p)].append(p)
    return dict(sorted(g.items()))


def group_by_time_interval(photos, gap_hours=4.0):
    """按时间间隔聚类：照片间隔 < gap_hours 归为同一事件。

    同一天但间隔超过 4 小时的照片会被拆成多个事件（如上午开会、下午工厂参观）。
    跨天但连续的夜间活动不会被拆开。
    返回 {date_key: [paths]} 格式，date_key 可能带 _2 _3 后缀。
    """
    # 获取每张照片的 datetime
    timed = []
    no_time = []
    for p in photos:
        dt = get_datetime(p)
        if dt:
            timed.append((dt, p))
        else:
            no_time.append(p)

    if not timed:
        return group_by_date(photos)

    # 按时间排序
    timed.sort(key=lambda x: x[0])

    # 分组：间隔 > gap_hours 断开
    clusters = []
    current = [timed[0]]
    for i in range(1, len(timed)):
        gap_h = (timed[i][0] - timed[i-1][0]).total_seconds() / 3600
        if gap_h > gap_hours:
            clusters.append(current)
            current = [timed[i]]
        else:
            current.append(timed[i])
    clusters.append(current)

    # 转为 {date_key: [paths]} 格式
    result = {}
    date_counter = defaultdict(int)
    for cluster in clusters:
        date_str = cluster[0][0].strftime("%Y-%m-%d")
        date_counter[date_str] += 1
        if date_counter[date_str] > 1:
            key = f"{date_str}_{date_counter[date_str]}"
        else:
            key = date_str
        result[key] = [p for _, p in cluster]

    # 无法获取时间的照片归入 unknown
    if no_time:
        result["unknown"] = result.get("unknown", []) + no_time

    return dict(sorted(result.items()))


# ═══════════════════════════════════════════
#  Ollama API
# ═══════════════════════════════════════════

def _ask(model, prompt, images=None, temp=0.3, max_tokens=200):
    payload = {
        "model": model, "prompt": prompt,
        "stream": False,
        "options": {"temperature": temp, "num_predict": max_tokens}
    }
    if images:
        payload["images"] = images
    r = requests.post(f"{OLLAMA}/api/generate", json=payload, timeout=180)
    if r.status_code == 200:
        return r.json().get("response", "").strip()
    raise ConnectionError(f"Ollama HTTP {r.status_code}")


# ═══════════════════════════════════════════
#  AI 分析器
# ═══════════════════════════════════════════

class EventAnalyzer:
    """AI 事件命名 + 照片标签分级（支持自定义标签 + 多标签）。"""

    def __init__(self, model, business_context="", grade_rules=None, tag_preset=None):
        self.model = model
        self.ctx = business_context.strip()
        # 多标签系统：tag_preset = {"tags": [...], "multi_tag": bool, "max_tags": int}
        self.tag_preset = tag_preset
        # 兼容旧版 ABC grade_rules
        self.grade_rules = grade_rules or {
            "A": "人物互动、情感表达、关键动作、独特场景",
            "B": "环境交代、背景细节、过渡场景",
            "C": "重复场景、模糊、空镜、文档",
        }

    # ── 事件命名 ──

    def name_event(self, date, sample_paths):
        """抽取最多 5 张样片让 AI 起名，返回名称字符串。"""
        if not sample_paths:
            return f"{date}_事件"

        # 分层取样：均匀取最多5张
        n = len(sample_paths)
        if n <= 5:
            indices = list(range(n))
        else:
            indices = [0, n // 4, n // 2, 3 * n // 4, n - 1]
        samples = [sample_paths[i] for i in indices if i < n][:5]

        imgs = []
        for p in samples:
            try:
                imgs.append(encode_image(p, max_size_kb=256))
            except Exception:
                pass
        if not imgs:
            return f"{date}_事件"

        ctx_line = f"\n\n【业务背景】{self.ctx}" if self.ctx else ""
        prompt = (
            f"你正在看一组拍摄于 {date} 的照片。{ctx_line}\n"
            f"请根据照片内容，给这一天的「事件」起一个简短名称（4-8个汉字，如：工厂考察、客户签约）。"
            f"只输出名称，不要解释。"
        )

        try:
            name = _ask(self.model, prompt, imgs, temp=0.2, max_tokens=20)
            name = re.sub(r'["""\'\n。，.!！]', '', name).strip()
            return name if len(name) >= 2 else f"{date}_事件"
        except Exception:
            return f"{date}_事件"

    # ── 照片分级 ──

    def _grade_prompt(self):
        """根据标签设定生成分级/标签提示词"""
        # 多标签模式
        if self.tag_preset:
            tags = self.tag_preset.get("tags", [])
            multi = self.tag_preset.get("multi_tag", False)
            max_tags = self.tag_preset.get("max_tags", 1)

            tag_lines = []
            for t in tags:
                name = t.get("name", "")
                desc = t.get("desc", "")
                tag_lines.append(f"  {name}：{desc}")
            tag_text = "\n".join(tag_lines)

            if multi:
                tag_instruction = f"从以上标签中选择最匹配的（最多{max_tags}个，逗号分隔）"
            else:
                tag_instruction = "从以上标签中选择最匹配的1个"

            return (
                "分析这张照片，按以下标签体系分类：\n"
                f"{tag_text}\n\n"
                f"{tag_instruction}\n\n"
                "严格按以下格式回复（不要额外文字）：\n"
                "TAGS: 标签1,标签2\n"
                "DESC: 简短中文描述(5-15字)\n"
                "STORY: 一句话故事点(15-30字，可直接用于短视频文案)"
            )

        # 兼容旧版 ABC 模式
        r = self.grade_rules
        return (
            "分析这张照片在业务场景中的「讲故事价值」，按以下标准分级：\n"
            f"A — 核心故事：{r.get('A', '人物互动、关键瞬间')}\n"
            f"B — 辅助场景：{r.get('B', '环境背景、过渡场景')}\n"
            f"C — 记录备查：{r.get('C', '重复、模糊、空镜')}\n\n"
            "严格按以下格式回复（不要额外文字）：\n"
            "GRADE: A/B/C\n"
            "DESC: 简短中文描述(5-12字)\n"
            "STORY: 一句话故事点(15-30字，可直接用于短视频文案)"
        )

    def grade_photo(self, image_path):
        """返回 {"grade":"A","tags":["工业","人物"],"desc":"...","story":"..."}。"""
        try:
            b64 = encode_image(image_path, max_size_kb=384)
        except Exception:
            return {"grade": "C", "tags": [], "desc": "无法读取", "story": ""}

        prompt = self._grade_prompt()
        if self.ctx:
            prompt += f"\n\n【业务背景】{self.ctx}\n请结合上述业务背景分析照片。"

        try:
            resp = _ask(self.model, prompt, [b64], temp=0.2, max_tokens=120)
        except Exception:
            return {"grade": "C", "tags": [], "desc": "AI 超时", "story": ""}

        result = {"grade": "C", "tags": [], "desc": "未知", "story": ""}
        for line in resp.split("\n"):
            line = line.strip()
            if line.upper().startswith("TAGS:"):
                raw = line.split(":", 1)[1].strip()
                if raw and raw != "无":
                    tags = [t.strip() for t in raw.replace("，", ",").split(",") if t.strip()]
                    result["tags"] = tags
                    # 兼容 grade 字段：取第一个标签
                    result["grade"] = tags[0] if tags else "C"
            elif line.upper().startswith("GRADE:"):
                g = line.split(":", 1)[1].strip().upper()
                result["grade"] = g if g in "ABC" else "C"
            elif line.upper().startswith("DESC:"):
                result["desc"] = line.split(":", 1)[1].strip()[:25]
            elif line.upper().startswith("STORY:"):
                result["story"] = line.split(":", 1)[1].strip()[:80]
        return result


# ═══════════════════════════════════════════
#  批量重命名器
# ═══════════════════════════════════════════

class BatchRenamer:
    """组织文件到 {output_base}/{date}_{event_name}/ 并重命名。"""

    @staticmethod
    def new_name(date, event, seq, grade, desc, ext, pattern=None, tags=None):
        """根据命名模板生成新文件名。

        pattern 为 None 时使用默认模板。
        支持的变量：{date} {event} {seq} {seq:02d} {grade} {desc} {ext} {tags}
        tags: 标签列表如 ["工业","人物"]，在文件名中用 - 连接
        """
        safe_ev = re.sub(r'[\\/:*?"<>|]', '', event)[:20]
        safe_ds = re.sub(r'[\\/:*?"<>|]', '', desc)[:15].replace(" ", "_")
        # 多标签：用 - 连接
        tags_str = "-".join(tags) if tags else grade

        if pattern:
            name = pattern
            name = name.replace("{date}", date)
            name = name.replace("{event}", safe_ev)
            name = name.replace("{grade}", grade)
            name = name.replace("{tags}", tags_str)
            name = name.replace("{desc}", safe_ds)
            name = name.replace("{ext}", ext)
            name = re.sub(r'\{seq(?::(\d+)d)?\}', lambda m: str(seq).zfill(int(m.group(1)) if m.group(1) else 0), name)
            if not name.endswith(ext):
                name += ext
            name = re.sub(r'[\\/:*?"<>|]', '', name)
            return name

        return f"{date}_{safe_ev}_{seq:02d}{tags_str}_{safe_ds}{ext}"

    @staticmethod
    def execute(photos, event_name, output_base, log=None, prog=None, pattern=None, collect=None):
        """
        photos: [(path, {"grade":"A","desc":"x","story":"y"}), ...]
        pattern: 自定义命名模板，None 时使用默认
        collect: 传入 list 时收集每个输出文件路径，供撤销使用
        返回 (success, fail)。
        """
        if not photos:
            return 0, 0

        date = get_date(photos[0][0])
        safe_ev = re.sub(r'[\\/:*?"<>|]', '', event_name)[:30]
        dir_ = os.path.join(output_base, f"{date}_{safe_ev}")
        os.makedirs(dir_, exist_ok=True)

        # 按标签优先级排序（兼容 ABC 和自定义标签）
        rank = {"A": 0, "B": 1, "C": 2}
        ordered = sorted(photos, key=lambda x: rank.get(x[1].get("grade", "C"), 2)
                         if x[1].get("grade", "C") in rank else 2)

        ok, ng = 0, 0
        for i, (path, info) in enumerate(ordered):
            try:
                grade = info.get("grade", "C")
                tags = info.get("tags", [])
                desc = info.get("desc", "未知")
                ext = os.path.splitext(path)[1].lower()

                name = BatchRenamer.new_name(date, safe_ev, i + 1, grade, desc, ext, pattern=pattern, tags=tags)
                dest = os.path.join(dir_, name)

                # 防重名
                if os.path.exists(dest):
                    base, e = os.path.splitext(name)
                    c = 1
                    while os.path.exists(dest):
                        dest = os.path.join(dir_, f"{base}_{c}{e}")
                        c += 1

                shutil.copy2(path, dest)
                if collect is not None:
                    collect.append(dest)
                ok += 1
                if prog:
                    prog(ok, len(ordered))
            except Exception as e:
                ng += 1
                if log:
                    log(f"    ❌ {os.path.basename(path)}: {e}")

        return ok, ng


# ═══════════════════════════════════════════
#  事件处理流水线
# ═══════════════════════════════════════════

class EventPipeline:
    """
    串联完整流程：
      scan → group_by_date → 逐事件 (name + grade + rename) → 断点保存

    dry_run=True 时只分析不重命名，供 UI 预览确认后手动执行。
    """

    def __init__(self, input_dir, output_dir, model, context="", force=False, dry_run=False, grade_rules=None, rename_pattern=None, tag_preset=None, min_photos=2, gap_hours=4.0, max_workers=3):
        self.input = input_dir
        self.output = output_dir
        self.model = model
        self.context = context
        self.force = force
        self.dry_run = dry_run
        self.rename_pattern = rename_pattern
        self.min_photos = min_photos
        self.gap_hours = gap_hours
        self.max_workers = max_workers

        self.analyzer = EventAnalyzer(model, context, grade_rules=grade_rules, tag_preset=tag_preset)
        self._stop = False
        self._events = []          # 本次新处理的事件
        self._skipped_dates = 0
        self._total_ok = 0
        self._total_ng = 0
        self._dests = []           # 本次生成的输出文件（供撤销）

    def stop(self):
        self._stop = True

    def undo(self):
        """撤销本次整理：删除生成的输出文件并清理空目录（原文件不受影响）。"""
        removed = 0
        dirs = set()
        for dest in self._dests:
            try:
                if os.path.exists(dest):
                    os.unlink(dest)
                    removed += 1
                dirs.add(os.path.dirname(dest))
            except OSError:
                pass
        for d in dirs:
            try:
                if os.path.isdir(d) and not os.listdir(d):
                    os.rmdir(d)
            except OSError:
                pass
        self._dests = []
        Checkpoint.clear(self.output)
        return removed

    def run(self, log=None, prog=None, on_event=None, overall=None):
        log = log or (lambda m: None)
        prog = prog or (lambda c, t: None)
        on_event = on_event or (lambda n, d: None)
        overall = overall or (lambda c, t: None)

        if self.force:
            Checkpoint.clear(self.output)
            log("🔄 强制模式：清除断点，从头开始")

        # 1. 扫描 & 分组
        log("📂 扫描照片...")
        photos = scan_photos(self.input)
        if not photos:
            log("❌ 无图片")
            return self

        log(f"📸 {len(photos)} 张")

        # 截图/转发图检测
        screenshots = [p for p in photos if is_screenshot(p)]
        if screenshots:
            log(f"📷 检测到 {len(screenshots)} 张可能的截图/转发图（无 EXIF，时间可能不准）")

        # 时间间隔聚类（同一天间隔 > 4h 的拆成多事件）
        if self.gap_hours > 0:
            groups = group_by_time_interval(photos, gap_hours=self.gap_hours)
            log(f"📅 {len(groups)} 个事件（{self.gap_hours}h 间隔聚类）")
        else:
            groups = group_by_date(photos)
            log(f"📅 {len(groups)} 个日期")

        # 合并照片数过少的分组（防止单张文件夹）
        if self.min_photos > 1:
            small_dates = {d: ps for d, ps in groups.items() if len(ps) < self.min_photos}
            if small_dates:
                log(f"🔗 发现 {len(small_dates)} 个小分组（<{self.min_photos}张），合并到相邻日期")
                for d, ps in small_dates.items():
                    all_dates = sorted(groups.keys())
                    idx = all_dates.index(d) if d in all_dates else -1
                    if idx > 0:
                        nearest = all_dates[idx - 1]
                    elif idx < len(all_dates) - 1:
                        nearest = all_dates[idx + 1]
                    else:
                        continue
                    groups[nearest].extend(ps)
                    del groups[d]
                    log(f"   {d} ({len(ps)}张) → 合并到 {nearest}")
                groups = dict(sorted(groups.items()))

        # 2. 断点检查
        done = Checkpoint.load(self.output)
        pending = {d: ps for d, ps in groups.items() if d not in done}
        if done:
            log(f"⏭ 跳过 {len(done)} 个已处理日期")

        if not pending:
            log("✅ 全部已处理")
            return self

        # 3. 逐事件处理
        total_evts = len(pending)
        for idx, (date, paths) in enumerate(pending.items()):
            if self._stop:
                log("⏹ 用户停止")
                break

            evt_num = idx + 1
            overall(evt_num, total_evts)
            log(f"\n{'─'*40}")
            log(f"📌 {evt_num}/{total_evts}  {date}  ({len(paths)}张)")

            # 3a. 命名（传入全部路径，由 name_event 内部分层取样）
            log("🤖 AI 命名事件...")
            name = self.analyzer.name_event(date, paths)
            log(f"   → {name}")

            if self._stop:
                break

            # 3b. 并发分级
            log(f"🔍 分级 {len(paths)} 张（{self.max_workers} 并发）...")
            results = [None] * len(paths)
            counts = {"A": 0, "B": 0, "C": 0}
            done_count = 0

            def _grade_one(idx_path):
                idx, p = idx_path
                return idx, self.analyzer.grade_photo(p)

            with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
                futures = {pool.submit(_grade_one, (i, p)): i
                           for i, p in enumerate(paths) if not self._stop}
                for future in as_completed(futures):
                    if self._stop:
                        break
                    try:
                        idx, r = future.result()
                    except Exception as e:
                        # 单张失败不拖垮整批：记录并继续
                        log(f"   ⚠️ 单张处理失败: {e}")
                        continue
                    results[idx] = (paths[idx], r)
                    g = r.get("grade", "C")
                    counts[g] = counts.get(g, 0) + 1
                    done_count += 1
                    if done_count % 5 == 0:
                        log(f"   {done_count}/{len(paths)}")
                    prog(done_count, len(paths))

            # 填充未完成的（被 stop 中断的）
            for i in range(len(results)):
                if results[i] is None:
                    results[i] = (paths[i], {"grade": "C", "tags": [], "desc": "跳过", "story": ""})

            log(f"   A={counts['A']}  B={counts['B']}  C={counts['C']}")
            on_event(name, len(paths))

            # 3c. 重命名（dry_run 跳过）
            ok = ng = 0
            if not self._stop and not self.dry_run:
                log("📝 重命名...")
                ok, ng = BatchRenamer.execute(
                    results, name, self.output, log=log, prog=prog,
                    pattern=self.rename_pattern, collect=self._dests
                )
                self._total_ok += ok
                self._total_ng += ng
                log(f"   ✅{ok} ❌{ng}")
            elif self.dry_run:
                log("👁 预览模式，跳过重命名")

            # 3d. 保存断点（dry_run 不保存）
            self._events.append({
                "date": date, "name": name, "total": len(paths),
                "results": results, "grades": counts, "ok": ok, "ng": ng,
            })
            if not self.dry_run:
                done.add(date)
                Checkpoint.save(self.output, done)

        # 4. 完成
        if not self._stop and not self.dry_run:
            Checkpoint.clear(self.output)
        log(f"\n{'─'*40}")
        if self.dry_run:
            log(f"👁 预览完成 {len(self._events)} 事件（未重命名）")
        else:
            log(f"🏁 完成 {len(self._events)} 事件  ✅{self._total_ok}  ❌{self._total_ng}")

        return self

    @property
    def events(self):
        return self._events

    @property
    def summary(self):
        """{total_events, total_photos, A, B, C, tags, success, fail}"""
        # 统计所有标签出现次数
        tag_counts = {}
        for e in self._events:
            for path, r in e.get("results", []):
                for t in r.get("tags", []):
                    tag_counts[t] = tag_counts.get(t, 0) + 1
                g = r.get("grade", "C")
                if g and not r.get("tags"):
                    tag_counts[g] = tag_counts.get(g, 0) + 1

        return {
            "events": len(self._events),
            "skipped": self._skipped_dates,
            "photos": sum(e["total"] for e in self._events),
            "A": sum(e["grades"].get("A", 0) for e in self._events),
            "B": sum(e["grades"].get("B", 0) for e in self._events),
            "C": sum(e["grades"].get("C", 0) for e in self._events),
            "tags": tag_counts,
            "success": self._total_ok,
            "fail": self._total_ng,
        }

    def confirm_execute(self, log=None, prog=None):
        """dry_run 分析后确认执行重命名。"""
        log = log or (lambda m: None)
        progn = prog or (lambda c, t: None)

        done = Checkpoint.load(self.output)
        ok_total = ng_total = 0
        for evt in self._events:
            ok, ng = BatchRenamer.execute(
                evt["results"], evt["name"], self.output, log=log, prog=progn,
                pattern=self.rename_pattern
            )
            ok_total += ok
            ng_total += ng
            done.add(evt["date"])
            Checkpoint.save(self.output, done)

        self._total_ok = ok_total
        self._total_ng = ng_total
        Checkpoint.clear(self.output)
        return ok_total, ng_total
