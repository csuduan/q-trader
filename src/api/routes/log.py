"""
日志API路由
提供日志查询和历史记录接口
"""
import os
from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import APIRouter

from src.api.responses import success_response
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/logs", tags=["日志"])


def get_today_log_file() -> str:
    """获取当天日志文件路径"""
    today = datetime.now().strftime("%Y-%m-%d")
    return f"data/logs/app_{today}.log"


def parse_log_line(line: str) -> dict:
    """解析日志行"""
    import re

    try:
        pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}) \| (\w+)\s+\| (.+?):(.+?):(\d+)\s*\| (.+)'
        match = re.match(pattern, line)

        if not match:
            return None

        return {
            "timestamp": match.group(1),
            "level": match.group(2),
            "logger": match.group(3),
            "function": match.group(4),
            "line": int(match.group(5)),
            "message": match.group(6),
        }
    except Exception as e:
        logger.debug(f"解析日志行失败: {e}")
        return None


@router.get("/history")
async def get_log_history(
    offset: int = 0,
    limit: int = 1000,
):
    """
    获取当天日志历史

    Args:
        offset: 偏移量（从末尾开始）
        limit: 返回条数限制

    Returns:
        日志条目列表（倒序，最新的在前）
    """
    log_file = get_today_log_file()

    if not os.path.exists(log_file):
        return success_response(
            data={"lines": [], "total": 0},
            message="日志文件不存在"
        )

    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()

        # 倒序获取
        lines = list(reversed(all_lines))

        # 应用偏移和限制
        end_index = offset + limit
        selected_lines = lines[offset:end_index]

        # 解析日志
        entries = []
        for line in selected_lines:
            line = line.strip()
            if not line:
                continue

            parsed = parse_log_line(line)
            if parsed:
                entries.append(parsed)

        return success_response(
            data={
                "lines": entries,
                "total": len(all_lines),
                "returned": len(entries)
            },
            message="获取成功"
        )
    except Exception as e:
        logger.error(f"读取日志文件失败: {e}")
        return success_response(
            data={"lines": [], "total": 0},
            message=f"读取失败: {str(e)}"
        )
