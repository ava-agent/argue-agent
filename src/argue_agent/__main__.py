"""Argue Agent - 实时辩论助手

启动方式:
    python -m argue_agent          # 启动 Web 服务
    python -m argue_agent --port 8080  # 指定端口
"""

import argparse
import logging
import socket

import uvicorn

from argue_agent.config import settings


def get_local_ip() -> str:
    """获取本机局域网IP地址"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main() -> None:
    parser = argparse.ArgumentParser(description="Argue Agent - 实时辩论助手")
    parser.add_argument("--host", default=settings.host, help="监听地址")
    parser.add_argument("--port", type=int, default=settings.port, help="监听端口")
    parser.add_argument("--debug", action="store_true", help="调试模式")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # 检查配置
    if not settings.glm_api_key:
        print("⚠️  未配置 GLM API Key！")
        print("   请在 .env 文件中设置 ARGUE_GLM_API_KEY")
        print("   或设置环境变量: export ARGUE_GLM_API_KEY=your-key")
        return

    if not settings.deepgram_api_key:
        print("ℹ️  未配置 Deepgram API Key，仅支持文本输入模式")
        print("   语音功能需要设置 ARGUE_DEEPGRAM_API_KEY")
        print()

    local_ip = get_local_ip()

    print(f"🚀 Argue Agent 启动中...")
    print(f"📱 手机访问: http://{local_ip}:{args.port}")
    print(f"💻 本机访问: http://localhost:{args.port}")
    print()

    uvicorn.run(
        "argue_agent.server:app",
        host=args.host,
        port=args.port,
        reload=args.debug,
    )


if __name__ == "__main__":
    main()
