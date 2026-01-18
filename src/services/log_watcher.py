"""
日志监控服务
监控日志文件变化并通过回调函数传递新日志
"""
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent

from src.utils.logger import get_logger

logger = get_logger(__name__)


class LogFileEventHandler(FileSystemEventHandler):
    """日志文件事件处理器"""

    def __init__(self, log_dir: str, on_modified: Callable[[str], None]):
        super().__init__()
        self.log_dir = log_dir
        self._on_modified_callback = on_modified

    def on_modified(self, event):
        """文件修改事件"""
        if event.is_directory:
            return

        file_path = event.src_path

        if not file_path.endswith('.log'):
            return

        if not file_path.startswith(self.log_dir):
            return

        logger.debug(f"检测到文件修改事件: {file_path}")
        self._on_modified_callback(file_path)


class LogWatcher:
    """日志监控器"""

    def __init__(self, log_dir: str, callback: Callable[[List[dict]], None]):
        """
        初始化日志监控器

        Args:
            log_dir: 日志目录
            callback: 新日志回调函数，接收日志列表
        """
        self.log_dir = log_dir
        self.callback = callback
        self.observer: Optional[Observer] = None
        self.file_position: Dict[str, int] = {}

    def start(self):
        """启动日志监控"""
        today_log_file = self._get_today_log_file()

        if os.path.exists(today_log_file):
            normalized_path = os.path.normpath(today_log_file)
            self.file_position[normalized_path] = os.path.getsize(today_log_file)
            logger.info(f"开始监控日志文件: {today_log_file}")

        self.observer = Observer()
        event_handler = LogFileEventHandler(self.log_dir, self._on_file_modified)
        self.observer.schedule(event_handler, self.log_dir, recursive=False)
        self.observer.start()
        logger.info("日志监控服务已启动")

    def stop(self):
        """停止日志监控"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
            self.file_position.clear()
            logger.info("日志监控服务已停止")

    def _get_today_log_file(self) -> str:
        """获取当天日志文件路径"""
        today = datetime.now().strftime("%Y-%m-%d")
        return os.path.join(self.log_dir, f"app_{today}.log")

    def _on_file_modified(self, file_path: str):
        """文件修改时处理"""
        if not file_path.endswith('.log'):
            return

        today_log_file = self._get_today_log_file()

        # 标准化路径比较（处理 Windows 路径分隔符问题）
        normalized_path = os.path.normpath(file_path)
        normalized_today = os.path.normpath(today_log_file)

        if normalized_path != normalized_today:
            return

        last_pos = self.file_position.get(normalized_path, 0)
        new_entries = self._read_new_lines(normalized_path, last_pos)

        if new_entries:
            logger.debug(f"检测到 {len(new_entries)} 条新日志")
            self.callback(new_entries)

    def _read_new_lines(self, file_path: str, start_pos: int) -> List[dict]:
        """读取文件新增内容"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                f.seek(start_pos)
                content = f.read()

            if not content:
                return []

            lines = content.split('\n')

            entries = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue

                parsed = self._parse_log_line(line)
                if parsed:
                    parsed['raw'] = line
                    entries.append(parsed)

            # 更新位置为文件末尾
            new_pos = start_pos + len(content)
            self.file_position[os.path.normpath(file_path)] = new_pos

            return entries
        except Exception as e:
            logger.error(f"读取日志文件失败 {file_path}: {e}")
            return []

    def _parse_log_line(self, line: str) -> Optional[dict]:
        """解析日志行"""
        try:
            pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}) \| (\w+)\s+\| (.+?):(.+?):(\d+)\s*\| (.+)'
            match = re.match(pattern, line)

            if not match:
                return None

            return {
                'timestamp': match.group(1),
                'level': match.group(2),
                'logger': match.group(3),
                'function': match.group(4),
                'line': int(match.group(5)),
                'message': match.group(6),
            }
        except Exception as e:
            logger.debug(f"解析日志行失败: {e}")
            return None
