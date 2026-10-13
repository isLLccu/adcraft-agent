"""不启动网页、不依赖数据库，直接跑一次 AI 核心。"""
import asyncio
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"backend"))
from app.ai.config import AISettings
from app.ai.provider import ModelClient
from app.ai.retrieval import Retriever
from app.ai.workflow import AIWorkflow


async def main():
    settings=AISettings()
    products=json.loads((ROOT/"data/sample_products.json").read_text(encoding="utf-8"))
    documents=json.loads((ROOT/"data/sample_documents.json").read_text(encoding="utf-8"))
    client=ModelClient(settings)
    workflow=AIWorkflow(settings,client,Retriever(settings,client))
    async def emit(type_,stage,message,data=None):
        print(f"[{stage}] {message}")
    result=await workflow.run(products[0],documents,"生成一版自然简洁的小红书文案，不添加未知保温时长。","xiaohongshu",[],emit)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=="__main__":
    asyncio.run(main())
