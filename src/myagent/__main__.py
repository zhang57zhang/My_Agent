"""MyAgent 入口点 — CLI 启动."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from myagent.core.config import MyAgentConfig
from myagent.engine.react import ReActEngine
from myagent.evolution.manager import EvolutionManager
from myagent.ui.terminal import TerminalUI


def setup_logging(verbose: bool = False) -> None:
    """配置日志."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def main() -> None:
    """CLI 入口函数."""
    parser = argparse.ArgumentParser(
        prog="myagent",
        description="MyAgent — 高效的终端 AI 编程助手",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="启用详细日志",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default=None,
        help="配置文件路径",
    )
    parser.add_argument(
        "-w",
        "--workdir",
        type=str,
        default=".",
        help="工作目录",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=None,
        help="LLM Provider (zhipu/qwen)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="模型 ID",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="API Key（也可通过环境变量 MYAGENT_API_KEY 设置）",
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    # 加载配置
    config = MyAgentConfig.load()
    if args.config:
        from pathlib import Path

        config = MyAgentConfig.load(Path(args.config))

    # 命令行参数覆盖
    import os

    if args.provider:
        config.default_provider = args.provider
    if args.api_key:
        if config.default_provider not in config.providers:
            config.providers[config.default_provider] = {}
        config.providers[config.default_provider]["api_key"] = args.api_key
    else:
        env_key = os.environ.get("MYAGENT_API_KEY", "")
        if env_key and config.default_provider not in config.providers:
            config.providers[config.default_provider] = {}
            config.providers[config.default_provider]["api_key"] = env_key

    if args.model:
        if config.default_provider not in config.providers:
            config.providers[config.default_provider] = {}
        config.providers[config.default_provider]["model_id"] = args.model

    # 确保配置了 API Key
    provider_cfg = config.providers.get(config.default_provider, {})
    if not provider_cfg.get("api_key"):
        print(f"[错误] 未配置 API Key。请通过以下方式之一配置：")
        print(f"  1. 设置环境变量: MYAGENT_API_KEY=your_key")
        print(f"  2. 命令行参数: --api-key your_key")
        print(f"  3. 配置文件: ~/.myagent/config.yaml")
        print(f"\n当前默认 Provider: {config.default_provider}")
        sys.exit(1)

    # 确保默认 Provider 配置完整
    if "provider_id" not in provider_cfg:
        config.providers[config.default_provider]["provider_id"] = config.default_provider
    if "model_id" not in provider_cfg:
        defaults = {"zhipu": "glm-4-plus", "qwen": "qwen-plus"}
        config.providers[config.default_provider]["model_id"] = defaults.get(
            config.default_provider, "glm-4-plus"
        )

    # 创建引擎和 UI
    engine = ReActEngine(config=config)

    # 启动 UI
    try:
        asyncio.run(TerminalUI(engine).start())
    except KeyboardInterrupt:
        print("\n再见！")


if __name__ == "__main__":
    main()
