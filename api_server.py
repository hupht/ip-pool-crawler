"""
REST API 服务器，用于暴露 IP 代理池爬虫的核心功能。
通过 `python cli.py server` 启动服务。
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, HttpUrl
import uvicorn

from crawler.dynamic_crawler import DynamicCrawler, crawl_custom_url, DynamicCrawlResult
from crawler.pipeline import run_once
from crawler.runtime import load_settings
from crawler.proxy_picker import pick_proxies
from tools import check_pool, diagnose_sources, diagnose_pipeline, get_proxy


# ============ 数据模型 ============

class CrawlCustomRequest(BaseModel):
    """自定义爬取请求"""
    url: HttpUrl = Field(..., description="目标URL")
    max_pages: Optional[int] = Field(1, description="最大页数", ge=1)
    use_ai: bool = Field(False, description="启用AI辅助")
    render_js: bool = Field(False, description="启用JS渲染(Playwright)")
    no_store: bool = Field(False, description="不存储到MySQL")
    verbose: bool = Field(False, description="详细输出")


class CrawlCustomResponse(BaseModel):
    """自定义爬取响应"""
    success: bool = Field(..., description="是否成功")
    url: str = Field(..., description="爬取的URL")
    session_id: Optional[int] = Field(None, description="会话ID")
    total_ips: int = Field(0, description="提取的IP总数")
    stored: int = Field(0, description="存储的IP数量")
    avg_confidence: float = Field(0.0, description="平均置信度")
    ai_calls_count: int = Field(0, description="AI调用次数")
    llm_cost_usd: float = Field(0.0, description="LLM成本（美元）")
    review_pending_count: int = Field(0, description="待审核数量")
    error: Optional[str] = Field(None, description="错误信息")


class GetProxyRequest(BaseModel):
    """获取代理请求"""
    count: int = Field(1, description="代理数量", ge=1, le=1000)
    protocol: Optional[str] = Field(None, description="协议类型: http, https, socks4, socks5")
    country: Optional[str] = Field(None, description="国家代码 (如 US, CN)")
    min_score: Optional[int] = Field(None, description="最小分数", ge=0, le=100)
    format: str = Field("json", description="输出格式: json, txt, csv")


class GetProxyResponse(BaseModel):
    """获取代理响应"""
    success: bool = Field(..., description="是否成功")
    count: int = Field(..., description="返回的代理数量")
    proxies: list[dict[str, Any]] = Field(..., description="代理列表")


class RunCrawlerRequest(BaseModel):
    """运行爬虫请求"""
    quick_test: bool = Field(False, description="快速测试模式")
    quick_record_limit: int = Field(1, description="快速模式记录限制", ge=1)


class RunCrawlerResponse(BaseModel):
    """运行爬虫响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="执行消息")


class CheckResponse(BaseModel):
    """代理检查响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="执行消息")


class DiagnoseResponse(BaseModel):
    """诊断响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="诊断信息")


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = Field("ok", description="服务状态")
    version: str = Field("1.0.0", description="API版本")


# ============ 全局状态 ============

class AppState:
    """应用状态"""
    def __init__(self):
        self.settings = None
        self.executor = ThreadPoolExecutor(max_workers=4)


app_state = AppState()


# ============ 生命周期管理 ============

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时加载配置
    try:
        app_state.settings = load_settings()
        print("✓ 配置加载成功")
    except Exception as e:
        print(f"✗ 配置加载失败: {e}")
        app_state.settings = None
    
    yield
    
    # 关闭时清理资源
    app_state.executor.shutdown(wait=True)
    print("✓ 资源清理完成")


# ============ FastAPI 应用 ============

app = FastAPI(
    title="IP代理池爬虫 API",
    description="提供代理爬取、检查、获取等功能的REST API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ============ 辅助函数 ============

def _check_settings():
    """检查配置是否已加载"""
    if app_state.settings is None:
        raise HTTPException(status_code=500, detail="配置未加载，请检查.env文件")


async def _run_in_thread(func, *args, **kwargs):
    """在线程池中运行阻塞函数"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(app_state.executor, func, *args, **kwargs)


# ============ API 路由 ============

@app.get("/", response_model=HealthResponse, tags=["系统"])
async def root():
    """根路径 - 健康检查"""
    return HealthResponse()


@app.get("/health", response_model=HealthResponse, tags=["系统"])
async def health_check():
    """健康检查端点"""
    return HealthResponse()


@app.post("/api/v1/crawl-custom", response_model=CrawlCustomResponse, tags=["爬虫"])
async def crawl_custom(request: CrawlCustomRequest):
    """
    爬取自定义URL的代理数据
    
    - **url**: 目标网页URL
    - **max_pages**: 最大爬取页数（默认1）
    - **use_ai**: 是否启用AI辅助解析（默认false）
    - **render_js**: 是否使用Playwright渲染JS（默认false）
    - **no_store**: 是否不存储到MySQL（默认false）
    - **verbose**: 是否输出详细日志（默认false）
    """
    _check_settings()
    
    if not app_state.settings.dynamic_crawler_enabled:
        raise HTTPException(status_code=403, detail="动态爬虫功能已禁用")
    
    try:
        # 在线程池中执行爬取
        def _crawl():
            return crawl_custom_url(
                settings=app_state.settings,
                url=str(request.url),
                max_pages=request.max_pages or app_state.settings.max_pages,
                use_ai=request.use_ai,
                no_store=request.no_store,
                verbose=request.verbose,
                render_js=request.render_js,
            )
        
        result: DynamicCrawlResult = await _run_in_thread(_crawl)
        
        # 获取会话统计信息
        response_data = {
            "success": result.stored > 0 or result.extracted > 0,
            "url": result.url,
            "session_id": result.session_id,
            "total_ips": result.extracted,
            "stored": result.stored,
            "avg_confidence": 0.0,
            "ai_calls_count": 0,
            "llm_cost_usd": 0.0,
            "review_pending_count": 0,
        }
        
        if result.session_id is not None:
            try:
                crawler = DynamicCrawler(app_state.settings)
                session_stats = crawler.get_session_stats(int(result.session_id))
                response_data["total_ips"] = session_stats.get("ip_count", result.extracted)
                response_data["avg_confidence"] = session_stats.get("avg_extraction_confidence", 0.0)
                response_data["ai_calls_count"] = session_stats.get("llm_calls", 0)
                response_data["llm_cost_usd"] = session_stats.get("llm_cost_usd", 0.0)
                response_data["review_pending_count"] = session_stats.get("review_pending_count", 0)
            except Exception:
                pass
        
        return CrawlCustomResponse(**response_data)
    
    except Exception as e:
        return CrawlCustomResponse(
            success=False,
            url=str(request.url),
            error=str(e)
        )


@app.post("/api/v1/run", response_model=RunCrawlerResponse, tags=["爬虫"])
async def run_crawler(request: RunCrawlerRequest, background_tasks: BackgroundTasks):
    """
    运行完整的爬虫流程（后台任务）
    
    - **quick_test**: 快速测试模式，只处理第一个成功的源
    - **quick_record_limit**: 快速模式下的记录限制
    """
    _check_settings()
    
    def _run():
        run_once(
            app_state.settings,
            quick_test=request.quick_test,
            quick_record_limit=request.quick_record_limit,
        )
    
    background_tasks.add_task(_run)
    
    return RunCrawlerResponse(
        success=True,
        message="爬虫任务已在后台启动"
    )


@app.post("/api/v1/check", response_model=CheckResponse, tags=["代理检查"])
async def check_proxies(background_tasks: BackgroundTasks):
    """
    运行TCP批量检查（后台任务）
    
    检查数据库中的所有代理，更新其连通性和分数
    """
    _check_settings()
    
    def _check():
        check_pool.run_check_batch(app_state.settings)
    
    background_tasks.add_task(_check)
    
    return CheckResponse(
        success=True,
        message="代理检查任务已在后台启动"
    )


@app.get("/api/v1/get-proxy", response_model=GetProxyResponse, tags=["代理获取"])
async def get_proxies(
    count: int = Query(1, ge=1, le=1000, description="代理数量"),
    protocol: Optional[str] = Query(None, description="协议: http, https, socks4, socks5"),
    country: Optional[str] = Query(None, description="国家代码"),
    min_score: Optional[int] = Query(None, ge=0, le=100, description="最小分数"),
):
    """
    从代理池获取代理
    
    - **count**: 获取的代理数量（1-1000）
    - **protocol**: 过滤协议类型
    - **country**: 过滤国家代码（如 US, CN）
    - **min_score**: 最小分数要求（0-100）
    """
    _check_settings()
    
    try:
        # 解析协议和国家参数
        protocols = [p.strip() for p in protocol.split(",")] if protocol else None
        countries = [c.strip() for c in country.split(",")] if country else None
        
        # 在线程池中获取代理
        def _get():
            return pick_proxies(
                settings=app_state.settings,
                protocols=protocols,
                countries=countries,
                count=count,
                require_check=True,
            )
        
        result = await _run_in_thread(_get)
        
        # 处理返回结果
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("message", "未知错误"))
        
        proxies_data = result.get("data", [])
        
        return GetProxyResponse(
            success=True,
            count=len(proxies_data),
            proxies=[
                {
                    "ip": p["ip"],
                    "port": p["port"],
                    "protocol": p["protocol"],
                    "country": p.get("country"),
                    "score": p.get("score", 0),
                    "last_ok": p.get("last_ok"),
                }
                for p in proxies_data
            ]
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取代理失败: {str(e)}")


@app.get("/api/v1/diagnose/sources", response_model=DiagnoseResponse, tags=["诊断"])
async def diagnose_sources_endpoint():
    """
    检查所有原始代理源的可用性
    
    返回每个源的HTTP状态和可访问性
    """
    _check_settings()
    
    try:
        # 捕获诊断输出
        import io
        import sys
        
        def _diagnose():
            old_stdout = sys.stdout
            sys.stdout = buffer = io.StringIO()
            try:
                diagnose_sources.run()
                return buffer.getvalue()
            finally:
                sys.stdout = old_stdout
        
        output = await _run_in_thread(_diagnose)
        
        return DiagnoseResponse(
            success=True,
            message=output
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"诊断失败: {str(e)}")


@app.get("/api/v1/diagnose/pipeline", response_model=DiagnoseResponse, tags=["诊断"])
async def diagnose_pipeline_endpoint():
    """
    检查数据管道（获取和解析）
    
    测试每个源的数据获取和解析能力
    """
    _check_settings()
    
    try:
        import io
        import sys
        
        def _diagnose():
            old_stdout = sys.stdout
            sys.stdout = buffer = io.StringIO()
            try:
                diagnose_pipeline.run()
                return buffer.getvalue()
            finally:
                sys.stdout = old_stdout
        
        output = await _run_in_thread(_diagnose)
        
        return DiagnoseResponse(
            success=True,
            message=output
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"诊断失败: {str(e)}")


# ============ 错误处理 ============

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """HTTP异常处理"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": exc.detail}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """通用异常处理"""
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": f"内部服务器错误: {str(exc)}"}
    )


# ============ 服务器启动函数 ============

def start_server(host: str = "0.0.0.0", port: int = 8000, env_path: str | None = None):
    """
    启动 API 服务器
    
    Args:
        host: 监听地址（默认 0.0.0.0）
        port: 监听端口（默认 8000）
        env_path: .env 文件路径
    """
    # 如果提供了 env_path，重新加载配置
    if env_path:
        app_state.settings = load_settings(env_path)
    
    print(f"🚀 启动 IP代理池 API 服务器...")
    print(f"📡 监听地址: http://{host}:{port}")
    print(f"📚 API文档: http://{host}:{port}/docs")
    print(f"📖 ReDoc文档: http://{host}:{port}/redoc")
    print(f"⚙️  配置文件: {env_path or '.env'}")
    print()
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    start_server()
