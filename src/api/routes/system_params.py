"""
系统参数相关API路由
"""
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.dependencies import get_db_session
from src.api.responses import success_response, error_response
from src.api.schemas import SystemParamRes, SystemParamUpdateReq
from src.database import get_database
from src.models.po import SystemParamPo
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/system-params", tags=["系统参数"])


@router.get("", response_model=List[SystemParamRes])
async def list_system_params(
    group: str | None = None,
    session: Session = Depends(get_db_session)
):
    """
    获取系统参数列表

    Args:
        group: 参数分组（可选）
        session: 数据库会话

    Returns:
        系统参数列表
    """
    try:
        query = session.query(SystemParamPo)

        if group:
            query = query.filter(SystemParamPo.group == group)

        params = query.order_by(SystemParamPo.group, SystemParamPo.param_key).all()

        return [SystemParamRes.model_validate(param) for param in params]

    except Exception as e:
        logger.error(f"获取系统参数失败: {e}", exc_info=True)
        return error_response(code=500, message=f"获取系统参数失败: {str(e)}")


@router.get("/{param_key}", response_model=SystemParamRes)
async def get_system_param(
    param_key: str,
    session: Session = Depends(get_db_session)
):
    """
    获取单个系统参数

    Args:
        param_key: 参数键名
        session: 数据库会话

    Returns:
        系统参数
    """
    try:
        param = session.query(SystemParamPo).filter(SystemParamPo.param_key == param_key).first()

        if not param:
            return error_response(code=404, message=f"参数 {param_key} 不存在")

        return SystemParamRes.model_validate(param)

    except Exception as e:
        logger.error(f"获取系统参数失败: {e}", exc_info=True)
        return error_response(code=500, message=f"获取系统参数失败: {str(e)}")


@router.put("/{param_key}")
async def update_system_param(
    param_key: str,
    req: SystemParamUpdateReq,
    session: Session = Depends(get_db_session)
):
    """
    更新系统参数

    Args:
        param_key: 参数键名
        req: 更新请求
        session: 数据库会话

    Returns:
        更新结果
    """
    try:
        param = session.query(SystemParamPo).filter(SystemParamPo.param_key == param_key).first()

        if not param:
            return error_response(code=404, message=f"参数 {param_key} 不存在")

        param.param_value = req.param_value
        param.updated_at = datetime.now()

        session.commit()
        session.refresh(param)

        logger.info(f"系统参数已更新: {param_key} = {req.param_value}")

        return success_response(
            data=SystemParamRes.model_validate(param),
            message="参数更新成功"
        )

    except Exception as e:
        session.rollback()
        logger.error(f"更新系统参数失败: {e}", exc_info=True)
        return error_response(code=500, message=f"更新系统参数失败: {str(e)}")


@router.get("/group/{group}")
async def get_system_params_by_group(
    group: str,
    session: Session = Depends(get_db_session)
):
    """
    根据分组获取系统参数

    Args:
        group: 参数分组
        session: 数据库会话

    Returns:
        系统参数字典
    """
    try:
        params = session.query(SystemParamPo).filter(SystemParamPo.group == group).all()

        result = {param.param_key: param.param_value for param in params}

        return success_response(data=result, message="获取成功")

    except Exception as e:
        logger.error(f"获取系统参数失败: {e}", exc_info=True)
        return error_response(code=500, message=f"获取系统参数失败: {str(e)}")
