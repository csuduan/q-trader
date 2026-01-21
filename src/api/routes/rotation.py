"""
换仓指令相关API路由
"""
import asyncio
import threading
from datetime import datetime
from typing import List, Optional
import io

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks
from pydantic import BaseModel

from src.api.dependencies import get_db_session, get_trading_engine
from src.api.responses import success_response, error_response
from src.models.po import RotationInstructionPo
from src.switch_mgr import SwitchPosManager
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/rotation", tags=["换仓指令"])


class RotationInstructionResponse(BaseModel):
    """换仓指令响应"""
    id: int
    account_id: Optional[str] = None
    strategy_id: Optional[str] = None
    symbol: Optional[str] = None
    exchange_id: Optional[str] = None
    offset: Optional[str] = None
    direction: Optional[str] = None
    volume: Optional[int] = 0
    filled_volume: Optional[int] = 0
    price: Optional[float] = 0
    order_time: Optional[str] = None
    trading_date: Optional[str] = None
    enabled: bool
    status: Optional[str] = None
    attempt_count: int = 0
    remaining_attempts: int = 0
    remaining_volume: int = 0
    current_order_id: Optional[str] = None
    order_placed_time: Optional[datetime] = None
    last_attempt_time: Optional[datetime] = None
    error_message: Optional[str] = None
    source: Optional[str] = None
    is_deleted: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RotationInstructionCreate(BaseModel):
    """创建换仓指令请求"""
    account_id: str
    strategy_id: str
    symbol: str
    exchange_id: str
    offset: str
    direction: str
    volume: int
    price: float = 0
    order_time: Optional[str] = None
    trading_date: Optional[str] = None
    enabled: bool = True


class RotationInstructionUpdate(BaseModel):
    """更新换仓指令请求"""
    enabled: Optional[bool] = None
    status: Optional[str] = None
    filled_volume: Optional[int] = None


@router.get("")
async def get_rotation_instructions(
    limit: int = 100,
    offset: int = 0,
    status: Optional[str] = None,
    enabled: Optional[bool] = None,
    session=Depends(get_db_session),
):
    """
    获取换仓指令列表

    - **limit**: 返回记录数量
    - **offset**: 偏移量
    - **status**: 状态筛选
    - **enabled**: 是否启用筛选
    """
    from src.context import get_switch_pos_manager

    switch_pos_manager = get_switch_pos_manager()
    rotation_status = {"working": False, "is_manual": False}
    instructions = []

    if switch_pos_manager and switch_pos_manager.working and switch_pos_manager.running_instructions:
        rotation_status["working"] = True
        rotation_status["is_manual"] = switch_pos_manager.is_manual
        instructions = switch_pos_manager.running_instructions
    else:
        today = datetime.now().strftime("%Y%m%d")
        query = session.query(RotationInstructionPo).filter_by(is_deleted=False, trading_date=today)

        if status:
            query = query.filter_by(status=status)

        if enabled is not None:
            query = query.filter_by(enabled=enabled)

        instructions = (
            query.order_by(RotationInstructionPo.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

    return success_response(
        data={
            "instructions": [RotationInstructionResponse.model_validate(ins) for ins in instructions],
            "rotation_status": rotation_status
        },
        message="获取成功"
    )


@router.get("/{instruction_id}")
async def get_rotation_instruction(
    instruction_id: int,
    session=Depends(get_db_session),
):
    """
    获取指定换仓指令

    - **instruction_id**: 指令ID
    """
    instruction = session.query(RotationInstructionPo).filter_by(
        id=instruction_id,
        is_deleted=False
    ).first()

    if not instruction:
        return error_response(code=404, message="换仓指令不存在")

    return success_response(
        data=RotationInstructionResponse.model_validate(instruction),
        message="获取成功"
    )


@router.post("")
async def create_rotation_instruction(
    request: RotationInstructionCreate,
    session=Depends(get_db_session),
):
    """
    创建换仓指令
    """
    trading_date = request.trading_date
    if not trading_date:
        trading_date = datetime.now().strftime("%Y%m%d")

    instruction = RotationInstructionPo(
        account_id=request.account_id,
        strategy_id=request.strategy_id,
        symbol=request.symbol,
        exchange_id=request.exchange_id,
        offset=request.offset,
        direction=request.direction,
        volume=request.volume,
        filled_volume=0,
        price=request.price,
        order_time=request.order_time,
        trading_date=trading_date,
        enabled=request.enabled,
        status="PENDING",
        attempt_count=0,
        remaining_attempts=0,
        remaining_volume=request.volume,
        current_order_id=None,
        order_placed_time=None,
        last_attempt_time=None,
        error_message=None,
        source="手动添加",
        created_at=datetime.now(),
        updated_at=datetime.now()
    )

    session.add(instruction)
    session.commit()
    session.refresh(instruction)

    return success_response(
        data=RotationInstructionResponse.model_validate(instruction),
        message="创建成功"
    )


@router.put("/{instruction_id}")
async def update_rotation_instruction(
    instruction_id: int,
    request: RotationInstructionUpdate,
    session=Depends(get_db_session),
):
    """
    更新换仓指令

    - **instruction_id**: 指令ID
    """
    instruction = session.query(RotationInstructionPo).filter_by(id=instruction_id).first()

    if not instruction:
        return error_response(code=404, message="换仓指令不存在")

    if request.enabled is not None:
        instruction.enabled = request.enabled

    if request.status is not None:
        instruction.status = request.status

    instruction.updated_at = datetime.now()

    session.add(instruction)
    session.commit()
    session.refresh(instruction)

    return success_response(
        data=RotationInstructionResponse.model_validate(instruction),
        message="更新成功"
    )


@router.delete("/{instruction_id}")
async def delete_rotation_instruction(
    instruction_id: int,
    session=Depends(get_db_session),
):
    """
    删除换仓指令（软删除）

    - **instruction_id**: 指令ID
    """
    instruction = session.query(RotationInstructionPo).filter_by(
        id=instruction_id,
        is_deleted=False
    ).first()

    if not instruction:
        return error_response(code=404, message="换仓指令不存在")

    instruction.is_deleted = True
    instruction.updated_at = datetime.now()

    session.add(instruction)
    session.commit()

    return error_response(code=204, message="删除成功")



@router.post("/clear")
async def clear_rotation_instructions(
    session=Depends(get_db_session),
):
    """
    清除已完成换仓指令（软删除）

    """

    session.query(RotationInstructionPo).filter(
        RotationInstructionPo.is_deleted == False,
        RotationInstructionPo.status == "COMPLETED",
    ).update(
        {"is_deleted": True, "updated_at": datetime.now()},
        synchronize_session=False
    )
    session.commit()
    return error_response(code=204, message="清除成功")


@router.post("/import", status_code=status.HTTP_201_CREATED)
async def import_rotation_instructions(
    file: UploadFile = File(...),
    mode: str = Form("append"),
    session=Depends(get_db_session),
):
    """
    批量导入换仓指令

    CSV格式：账户编号,策略编号,合约,开平,方向,手数,报单时间(可选)
    例如：DQ,StrategyFix_PK,PK603.CZC,Close,Sell,2,09:05:00

    文件名格式支持：yyyyMMdd_*.csv，用于提取交易日
    例如：20250115_rotation.csv，将提取交易日期为20250115

    - **file**: CSV文件
    - **mode**: 导入模式，append(追加) 或 replace(替换)
    """
    from src.context import get_switch_pos_manager
    switch_pos_manager = get_switch_pos_manager()
    content = await file.read()
    csv_text = content.decode("gbk")
    res = switch_pos_manager.import_csv(csv_text,file.filename, mode)
    return success_response(
        data=res,
        message="导入完成"
    )


class BatchRequest(BaseModel):
    """批量操作请求"""
    ids: List[int]


@router.post("/batch/execute")
async def batch_execute_instructions(
    request: BatchRequest,
    session=Depends(get_db_session),
):
    """
    批量执行换仓指令

    - **request**: 包含指令ID列表的请求体
    """
    instructions = session.query(RotationInstructionPo).filter(
        RotationInstructionPo.id.in_(request.ids),
        RotationInstructionPo.is_deleted == False
    ).all()

    if not instructions:
        return error_response(code=404, message="未找到任何换仓指令")

    success_count = 0
    failed_count = 0

    for instruction in instructions:
        if not instruction.enabled:
            failed_count += 1
            continue

        if instruction.status == "COMPLETED":
            failed_count += 1
            continue

        try:
            instruction.status = "EXECUTING"
            instruction.last_attempt_time = datetime.now()
            instruction.attempt_count += 1
            instruction.updated_at = datetime.now()

            session.add(instruction)
            success_count += 1

        except Exception as e:
            logger.error(f"执行指令失败: {e}")
            failed_count += 1

    session.commit()

    return success_response(
        data={
            "success": success_count,
            "failed": failed_count,
            "total": len(instructions)
        },
        message=f"执行完成：成功 {success_count} 条，失败 {failed_count} 条"
    )


@router.post("/batch/delete")
async def batch_delete_instructions(
    request: BatchRequest,
    session=Depends(get_db_session),
):
    """
    批量删除换仓指令（软删除）

    - **request**: 包含指令ID列表的请求体
    """
    deleted_count = session.query(RotationInstructionPo).filter(
        RotationInstructionPo.id.in_(request.ids)
    ).update(
        {"is_deleted": True, "updated_at": datetime.now()},
        synchronize_session=False
    )

    session.commit()

    return success_response(
        data={"deleted": deleted_count},
        message="删除成功"
    )


@router.post("/start")
async def start_rotation():
        """
        启动换仓流程（异步执行）
        """
        try:
            from src.context import get_trading_engine
            from src.context import get_switch_pos_manager

            trading_engine = get_trading_engine()

            if not trading_engine:
                return error_response(code=500, message="交易引擎未初始化")


            def execute_rotation():
                """后台线程执行换仓任务"""
                try:
                    position_manager = get_switch_pos_manager()
                    position_manager.execute_position_rotation(is_manual=True)
                    logger.info("换仓任务执行完成")
                except Exception as e:
                    logger.error(f"后台换仓任务执行失败: {e}")

            thread = threading.Thread(target=execute_rotation, daemon=True)
            thread.start()

            return success_response(
                data={},
                message="换仓流程已在后台启动"
            )

        except Exception as e:
            logger.error(f"启动换仓流程失败: {e}")
            return error_response(code=500, message=f"启动换仓流程失败: {str(e)}")
