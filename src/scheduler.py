"""
定时任务调度器模块
使用APScheduler管理定时任务
"""
import time
from datetime import datetime
from typing import Callable, List, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.config_loader import AppConfig
from src.database import get_session
from src.job_mgr import JobManager
from src.models.po import JobPo as JobModel
from src.switch_mgr import SwitchPosManager
from src.trading_engine import TradingEngine
from src.utils.logger import get_logger

logger = get_logger(__name__)


class TaskScheduler:
    """任务调度器类"""

    def __init__(self, config: AppConfig, trading_engine: TradingEngine):
        """
        初始化任务调度器

        Args:
            config: 应用配置
            trading_engine: 交易引擎实例
        """
        self.config = config
        self.trading_engine = trading_engine
        self.scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
        self.position_manager = SwitchPosManager(config, trading_engine)
        self.job_manager = JobManager(config, trading_engine, self.position_manager)

        # 初始化任务配置到数据库
        self._init_jobs_in_db()

        # 从数据库加载任务配置并设置定时任务
        self._setup_jobs_from_db()

        logger.info("任务调度器初始化完成")

    def _init_jobs_in_db(self) -> None:
        """初始化任务配置到数据库"""
        session = get_session()
        if not session:
            logger.error("无法获取数据库会话")
            return

        # 从config.yaml获取任务配置
        default_jobs = []
        if self.config and self.config.scheduler and self.config.scheduler.jobs:
            default_jobs = [
                {
                    "job_id": job.job_id,
                    "job_name": job.job_name,
                    "job_group": job.job_group,
                    "job_description": job.job_description,
                    "cron_expression": job.cron_expression,
                    "job_method": job.job_method,
                    "enabled": job.enabled,
                }
                for job in self.config.scheduler.jobs
            ]

        try:
            for job_config in default_jobs:
                existing_job = session.query(JobModel).filter_by(job_id=job_config["job_id"]).first()
                if not existing_job:
                    job = JobModel(
                        job_id=job_config["job_id"],
                        job_name=job_config["job_name"],
                        job_group=job_config["job_group"],
                        job_description=job_config["job_description"],
                        cron_expression=job_config["cron_expression"],
                        job_method=job_config["job_method"],
                        enabled=job_config["enabled"],
                    )
                    session.add(job)
                    logger.info(f"已创建任务配置: {job_config['job_name']}")
                else:
                    # 更新现有任务配置（从config.yaml同步）
                    existing_job.job_name = job_config["job_name"]
                    existing_job.job_group = job_config["job_group"]
                    existing_job.job_description = job_config["job_description"]
                    existing_job.cron_expression = job_config["cron_expression"]
                    existing_job.job_method = job_config["job_method"]
                    existing_job.enabled = job_config["enabled"]
                    session.merge(existing_job)

            session.commit()
            logger.info(f"已从配置文件同步 {len(default_jobs)} 个任务配置到数据库")
        except Exception as e:
            logger.error(f"初始化任务配置到数据库失败: {e}")
            session.rollback()
        finally:
            session.close()

    def _setup_jobs_from_db(self) -> None:
        """从数据库加载任务配置并设置定时任务"""
        session = get_session()
        if not session:
            logger.error("无法获取数据库会话")
            return

        try:
            jobs = session.query(JobModel).all()

            for job in jobs:
                # 获取job_method值
                job_method_value = getattr(job, "job_method", None)

                # 跳过job_method为空的记录
                if not job_method_value or job_method_value == "":
                    logger.warning(f"任务 {job.job_name} 缺少执行方法，跳过")
                    continue

                # 从 job_manager 动态获取执行方法
                # 去掉方法名前的下划线，如 _pre_market_connect -> pre_market_connect
                method_name = job_method_value.lstrip("_")
                job_func = getattr(self.job_manager, method_name, None)

                if not job_func or not callable(job_func):
                    logger.error(f"任务 {job.job_name} 的执行方法 {method_name} 不存在，跳过")
                    continue

                # 包装任务函数，在执行后更新触发时间
                def wrap_job_func(func: Callable, job_id: str) -> Callable:
                    def wrapped():
                        try:
                            func()
                        finally:
                            self._update_job_last_trigger_time(job_id)
                    return wrapped

                wrapped_func = wrap_job_func(job_func, str(job.job_id))

                # 解析CRON表达式，支持5字段和6字段格式
                cron_parts = job.cron_expression.split()
                if len(cron_parts) == 6:
                    # 6字段格式：秒 分 时 日 月 周
                    trigger = CronTrigger(
                        second=cron_parts[0],
                        minute=cron_parts[1],
                        hour=cron_parts[2],
                        day=cron_parts[3],
                        month=cron_parts[4],
                        day_of_week=cron_parts[5],
                        timezone="Asia/Shanghai",
                    )
                else:
                    # 5字段格式：分 时 日 月 周
                    trigger = CronTrigger.from_crontab(job.cron_expression, timezone="Asia/Shanghai")

                self.scheduler.add_job(
                    wrapped_func,
                    trigger,
                    id=job.job_id,
                    name=job.job_name,
                    replace_existing=True,
                )
                if not job.enabled:
                    self.scheduler.pause_job(job.job_id)
                logger.info(f"已添加任务: {job.job_name}, 方法: {job_method_value}, CRON: {job.cron_expression}, 状态: {'暂停' if not job.enabled else '运行'}")

            logger.info(f"已从数据库加载 {len(jobs)} 个任务配置")
        except Exception as e:
            logger.error(f"从数据库加载任务配置失败: {e}")
        finally:
            session.close()

    def start(self) -> None:
        """启动调度器"""
        try:
            self.scheduler.start()
            logger.info("任务调度器已启动")
        except Exception as e:
            logger.error(f"启动任务调度器失败: {e}")

    def shutdown(self) -> None:
        """关闭调度器"""
        try:
            self.scheduler.shutdown(wait=False)
            logger.info("任务调度器已关闭")
        except Exception as e:
            logger.error(f"关闭任务调度器时出错: {e}")

    def get_jobs(self) -> List[dict]:
        """
        获取所有任务信息

        Returns:
            List[dict]: 任务信息列表
        """
        jobs = []
        for job in self.scheduler.get_jobs():
            next_run_time_val = None
            if job.next_run_time:
                try:
                    next_run_time_val = job.next_run_time.isoformat()
                except:
                    next_run_time_val = str(job.next_run_time)

            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": next_run_time_val,
            })
        return jobs

    def trigger_job(self, job_id: str) -> bool:
        """
        手动触发定时任务

        Args:
            job_id: 任务ID

        Returns:
            bool: 是否触发成功
        """
        try:
            job = self.scheduler.get_job(job_id)
            if not job:
                logger.error(f"任务不存在: {job_id}")
                return False

            # 立即执行任务（使用一次性的调度）
            self.scheduler.add_job(
                job.func,
                trigger='date',
                id=f"{job_id}_manual_{int(datetime.now().timestamp())}",
                name=f"{job.name} (手动)",
            )

            # 更新最后触发时间到数据库
            self._update_job_last_trigger_time(job_id)

            logger.info(f"已手动触发任务: {job.name} ({job_id})")
            return True
        except Exception as e:
            logger.error(f"触发任务失败: {job_id}, 错误: {e}")
            return False

    def operate_job(self, job_id: str, action: str) -> bool:
        """
        操作定时任务（暂停/恢复/触发）

        Args:
            job_id: 任务ID
            action: 操作类型（pause/resume/trigger）

        Returns:
            bool: 是否操作成功
        """
        session = get_session()
        if not session:
            logger.error("无法获取数据库会话")
            return False

        try:
            job = session.query(JobModel).filter_by(job_id=job_id).first()
            if not job:
                logger.error(f"任务不存在: {job_id}")
                return False

            apscheduler_job = self.scheduler.get_job(job_id)
            if not apscheduler_job:
                logger.error(f"调度器中找不到任务: {job_id}")
                return False

            if action == "pause":
                apscheduler_job.pause()
                job.enabled = False
                job.updated_at = datetime.now()
                session.add(job)
                session.commit()
                logger.info(f"暂停任务: {job.job_name} ({job_id})")
                return True
            elif action == "resume":
                apscheduler_job.resume()
                job.enabled = True
                job.updated_at = datetime.now()
                session.add(job)
                session.commit()
                logger.info(f"恢复任务: {job.job_name} ({job_id})")
                return True
            elif action == "trigger":
                success = self.trigger_job(job_id)
                return success
            else:
                logger.error(f"未知操作: {action}")
                return False
        except Exception as e:
            logger.error(f"操作任务失败: {job_id}, 错误: {e}")
            session.rollback()
            return False
        finally:
            session.close()

    def _update_job_last_trigger_time(self, job_id: str) -> None:
        """
        更新任务最后触发时间到数据库

        Args:
            job_id: 任务ID
        """
        session = get_session()
        if not session:
            logger.error("无法获取数据库会话")
            return

        try:
            job = session.query(JobModel).filter_by(job_id=job_id).first()
            if job:
                job.last_trigger_time = datetime.now()
                session.add(job)
                session.commit()
        except Exception as e:
            logger.error(f"更新任务最后触发时间失败: {job_id}, 错误: {e}")
            session.rollback()
        finally:
            session.close()

    def update_job_status(self, job_id: str, enabled: bool) -> bool:
        """
        更新任务启用状态到数据库

        Args:
            job_id: 任务ID
            enabled: 是否启用

        Returns:
            bool: 是否更新成功
        """
        session = get_session()
        if not session:
            logger.error("无法获取数据库会话")
            return False

        try:
            job = session.query(JobModel).filter_by(job_id=job_id).first()
            if not job:
                logger.error(f"任务不存在: {job_id}")
                return False

            job.enabled = enabled
            job.updated_at = datetime.now()
            session.add(job)
            session.commit()

            logger.info(f"任务 {job.job_name} ({job_id}) 已{'启用' if enabled else '禁用'}")
            return True
        except Exception as e:
            logger.error(f"更新任务状态失败: {job_id}, 错误: {e}")
            session.rollback()
            return False
        finally:
            session.close()
