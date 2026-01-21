"""
策略管理API路由
提供策略CRUD、启停、参数配置接口
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends

from src.api.responses import success_response, error_response
from src.api.dependencies import get_trading_engine
from src.models.object import StrategyType

router = APIRouter(prefix="/strategies", tags=["策略管理"])


@router.get("")
async def list_strategies(trading_engine=Depends(get_trading_engine)):
    """
    获取策略列表

    Returns:
        策略状态列表
    """
    try:
        if not hasattr(trading_engine, 'strategy_manager'):
            return success_response(data=[])

        strategies = trading_engine.get_strategy_status()
        return success_response(data=strategies)
    except Exception as e:
        return error_response(message=f"获取策略列表失败: {str(e)}")


@router.get("/{strategy_id}")
async def get_strategy(strategy_id: str, trading_engine=Depends(get_trading_engine)):
    """
    获取指定策略状态

    Args:
        strategy_id: 策略ID

    Returns:
        策略状态
    """
    try:
        if not hasattr(trading_engine, 'strategy_manager'):
            raise HTTPException(status_code=404, detail="策略系统未初始化")

        if strategy_id not in trading_engine.strategy_manager.strategies:
            raise HTTPException(status_code=404, detail=f"策略不存在: {strategy_id}")

        strategy = trading_engine.strategy_manager.strategies[strategy_id]
        return success_response(data={
            "strategy_id": strategy.strategy_id,
            "active": strategy.active,
            "config": strategy.config
        })
    except HTTPException:
        raise
    except Exception as e:
        return error_response(message=f"获取策略状态失败: {str(e)}")


@router.post("/{strategy_id}/start")
async def start_strategy(strategy_id: str, trading_engine=Depends(get_trading_engine)):
    """
    启动指定策略

    Args:
        strategy_id: 策略ID

    Returns:
        操作结果
    """
    try:
        if not hasattr(trading_engine, 'strategy_manager'):
            raise HTTPException(status_code=404, detail="策略系统未初始化")

        success = trading_engine.strategy_manager.start_strategy(strategy_id)
        if success:
            return success_response(message=f"策略 {strategy_id} 启动成功")
        else:
            raise HTTPException(status_code=400, detail=f"启动策略失败: {strategy_id}")
    except HTTPException:
        raise
    except Exception as e:
        return error_response(message=f"启动策略失败: {str(e)}")


@router.post("/{strategy_id}/stop")
async def stop_strategy(strategy_id: str, trading_engine=Depends(get_trading_engine)):
    """
    停止指定策略

    Args:
        strategy_id: 策略ID

    Returns:
        操作结果
    """
    try:
        if not hasattr(trading_engine, 'strategy_manager'):
            raise HTTPException(status_code=404, detail="策略系统未初始化")

        success = trading_engine.strategy_manager.stop_strategy(strategy_id)
        if success:
            return success_response(message=f"策略 {strategy_id} 停止成功")
        else:
            raise HTTPException(status_code=400, detail=f"停止策略失败: {strategy_id}")
    except HTTPException:
        raise
    except Exception as e:
        return error_response(message=f"停止策略失败: {str(e)}")


@router.post("/start-all")
async def start_all_strategies(trading_engine=Depends(get_trading_engine)):
    """
    启动所有已启用的策略

    Returns:
        操作结果
    """
    try:
        if not hasattr(trading_engine, 'strategy_manager'):
            raise HTTPException(status_code=404, detail="策略系统未初始化")

        trading_engine.start_all_strategies()
        return success_response(message="已启动所有策略")
    except HTTPException:
        raise
    except Exception as e:
        return error_response(message=f"启动策略失败: {str(e)}")


@router.post("/stop-all")
async def stop_all_strategies(trading_engine=Depends(get_trading_engine)):
    """
    停止所有策略

    Returns:
        操作结果
    """
    try:
        if not hasattr(trading_engine, 'strategy_manager'):
            raise HTTPException(status_code=404, detail="策略系统未初始化")

        trading_engine.stop_all_strategies()
        return success_response(message="已停止所有策略")
    except HTTPException:
        raise
    except Exception as e:
        return error_response(message=f"停止策略失败: {str(e)}")
