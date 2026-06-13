import asyncio
import tiktoken
from openai import AsyncOpenAI
from app.services.cleanup import collapse_whitespace
import re

async def clean_chunk(client: AsyncOpenAI, chunk_text: str, index: int, total: int, model: str, aggressiveness: int) -> str:
    if aggressiveness == 1:
        # Conservative bypasses TOC/References removal prompt
        extra_prompt = ""
    else:
        extra_prompt = """
        5. 额外规则：识别与剔除目录与参考文献
           - 如果当前块整体就是目录（开头有"目录"/"Contents"等，且内容是页码/章节列表），直接返回空文本。
           - 如果当前块整体就是参考文献（开头是"参考文献"/"References"等，且内容是引用条目），直接返回空文本。
           - 禁止仅凭关键词就判定为目录/参考文献。出现正文用法必须保留。
        """

    system_prompt = f"""你是一个专业的文档编辑专家。你的任务是清洗以下 Markdown 文本分块：
    1. 去除所有不属于正文的冗余信息，包括：页眉、页脚、页码。
    2. 修正因 OCR 解析产生的拼接错误或断行。除补回漏字外，绝对不能修改、润色或增删正文的核心原意。
    3. 保持 Markdown 格式完整性（特别是标题层级 #, ##，表格，列表）。
    4. 严格只返回清洗后的 Markdown 文本，不要包含任何旁白、解释或 ```markdown 标记。
    5. 注意：部分文本块开头可能包含 `> [上下文: XXX > YYY]` 的辅助信息，这是为了帮助你理解当前段落的背景。在最终输出的文本中，**必须将这些辅助的上下文提示语彻底删除，不要保留它们**。
    {extra_prompt}
    """

    user_content = f"[Doc2MD Context]\n- 当前分块索引: {index} / {total}\n[/Doc2MD Context]\n\n{chunk_text}"

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.0
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        # Degradation: return original text if LLM call fails
        return chunk_text

async def reconstruct_image_vlm(
    client: AsyncOpenAI, 
    abs_path: str, 
    ext: str, 
    model: str, 
    keep_original: bool,
    rel_url: str = ""
) -> str:
    import base64
    import os
    
    # Check if the file exists
    if not os.path.exists(abs_path):
        return f"![Image Not Found]({rel_url})"
        
    try:
        with open(abs_path, "rb") as image_file:
            base_64_data = base64.b64encode(image_file.read()).decode('utf-8')
    except Exception:
        return f"![Image Error]({rel_url})"
        
    image_url = f"data:image/{ext};base64,{base_64_data}"
    
    # 步骤 1: 图像分类器 (Classifier Channel)
    classifier_system = """你是一个图像分类专家。请分析传入的图片，严格只返回以下 8 个英文标签之一，不要包含任何其他字符：
    - "table" (表格)
    - "flowchart_diagram" (流程图/架构图/思维导图)
    - "chart_graph" (折线/柱状/饼图等统计图)
    - "formula" (数学/化学公式)
    - "ui_screenshot" (软件/网页截图)
    - "photo_illustration" (实物照片/插图)
    - "signature_stamp" (签名/盖章)
    - "decorative" (装饰线/LOGO/无意义图标)
    """
    
    try:
        cls_resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": classifier_system},
                {"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]}
            ],
            temperature=0.0,
            max_tokens=10
        )
        label = cls_resp.choices[0].message.content.strip().lower()
    except Exception:
        label = "photo_illustration" # 降级为普通描述

    # 步骤 2: 分流调用专业 Prompt (Specialized Worker Channel)
    prompts = {
        "table": "请将这张图片中的表格还原为高保真的标准 Markdown 表格格式（如 | col1 | col2 |）。只返回表格文本，不要任何解释或 markdown 标记。",
        "flowchart_diagram": "请将这张流程图/架构图/思维导图转换为完美的 Mermaid.js 格式代码。严格使用 ```mermaid 标记包裹。只返回 Mermaid 代码，不要任何解释。",
        "chart_graph": "请分析这张统计图表，提取其底层的定量数据，输出一个 Markdown 数据表格，并在下方配以一句话核心趋势总结。",
        "formula": "请将这张复杂的数学或化学公式还原为 LaTeX 语法格式（使用 $$ 包裹）。只返回 LaTeX 代码，不要任何解释。",
        "ui_screenshot": "请详细描述这张软件/网页截图中的界面元素、当前状态，并以有序列表输出交互操作步骤推导。",
        "photo_illustration": "请为这张插图或照片生成一段高保真的 alt-text 语义描述，阐明主体、动作和环境。",
        "signature_stamp": "请识别并提取图中的合规与签署信息，返回格式如：[元数据: 包含 XXX 的签名/盖章]。",
        "decorative": "" # 装饰性直接剔除
    }
    
    prompt = prompts.get(label, prompts["photo_illustration"])
    if not prompt:
        return "" # 装饰图直接删除

    try:
        reconstruct_resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一个专业的图像结构化与重构专家。"},
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]}
            ],
            temperature=0.0
        )
        reconstructed_text = reconstruct_resp.choices[0].message.content.strip()
        
        # 将原图链接附在后面？用户说要把 description 插入到上下文。
        # 我们可以保留原图并在其下方加上描述
        if keep_original:
            return f"\n\n![{label}]({rel_url})\n\n> **AI Vision:** {reconstructed_text}\n\n"
        else:
            return f"\n\n{reconstructed_text}\n\n"
    except Exception:
        # 降级：如果重构失败，保持原图片链接
        return f"![Figure]({rel_url})"

def chunk_markdown(text: str, max_tokens: int) -> list[str]:
    enc = tiktoken.get_encoding("cl100k_base")
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = []
    current_length = 0
    hierarchy = {}
    
    for p in paragraphs:
        # 追踪标题层级
        heading_match = re.match(r'^(#{1,6})\s+(.*)$', p.strip())
        if heading_match:
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            hierarchy[level] = title
            # 清理更深层级的过时标题
            for l in list(hierarchy.keys()):
                if l > level:
                    del hierarchy[l]
                    
        p_len = len(enc.encode(p))
        
        # 如果当前块将超出限制，则截断保存
        if current_length + p_len > max_tokens and current_chunk:
            chunks.append("\n\n".join(current_chunk))
            
            # 为新区块注入上下文的面包屑导航
            context_header = []
            if hierarchy:
                breadcrumbs = " > ".join([hierarchy[k] for k in sorted(hierarchy.keys())])
                context_header.append(f"> [上下文: {breadcrumbs}]")
            
            current_chunk = context_header + [p] if context_header else [p]
            current_length = len(enc.encode("\n\n".join(current_chunk)))
        else:
            current_chunk.append(p)
            current_length += p_len
            
    if current_chunk:
        chunks.append("\n\n".join(current_chunk))
        
    return chunks



async def clean_document_llm(
    raw_md: str,
    job_dir: str = "",
    api_key: str = "",
    base_url: str = "",
    model: str = "gpt-4o-mini",
    aggressiveness: int = 1,
    max_tokens: int = 2048,
    concurrency: int = 3,
    progress_callback: callable = None,
    use_vlm: bool = False,
    keep_original_images: bool = False,
    prompt_extension: str = ""
) -> str:
    """
    Cleans raw markdown from MinerU by chunking and sending to LLM.
    Also handles VLM image reconstruction via DOC2MD_IMG_xxx.
    """

    # 1. 提取本地图片链接并使用唯一占位符替换
    # 匹配 MinerU 输出的图片链接：![alt](images/xxx.jpg)
    import os
    pattern = r'!\[(.*?)\]\((images\/[^\)]+\.(?P<ext>jpg|png|jpeg))(?:\s+"([^"]*)")?\)'
    matches = list(re.finditer(pattern, raw_md, re.IGNORECASE))
    
    image_dict = {}
    placeholder_md = raw_md
    
    for i, m in enumerate(matches):
        placeholder = f"![image_placeholder](DOC2MD_IMG_{i})"
        rel_path = m.group(2)
        ext = m.group("ext").lower()
        abs_path = os.path.join(job_dir, rel_path) if job_dir else rel_path
        
        image_dict[placeholder] = {
            "full_match": m.group(0),
            "alt": m.group(1),
            "url": rel_path,
            "abs_path": abs_path,
            "ext": ext
        }
        placeholder_md = placeholder_md.replace(m.group(0), placeholder)

    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    enc = tiktoken.get_encoding("cl100k_base")
    total_tokens = len(enc.encode(placeholder_md))

    # 步骤 2: 纯文本清洗
    if total_tokens <= max_tokens:
        cleaned_md = await clean_chunk(client, placeholder_md, 1, 1, model, aggressiveness)
    else:
        chunks = chunk_markdown(placeholder_md, max_tokens)
        total_chunks = len(chunks)
        semaphore = asyncio.Semaphore(concurrency)
        
        async def sem_clean(chunk_text, idx):
            async with semaphore:
                res = await clean_chunk(client, chunk_text, idx, total_chunks, model, aggressiveness)
                if progress_callback:
                    progress_callback(idx, total_chunks)
                return res

        tasks = [sem_clean(chunk, i + 1) for i, chunk in enumerate(chunks)]
        cleaned_chunks = await asyncio.gather(*tasks)
        cleaned_md = "\n\n".join([c for c in cleaned_chunks if c])
        
    cleaned_md = collapse_whitespace(cleaned_md)

    # 步骤 3: 回填与 VLM 重构
    if use_vlm:
        # 如果开启了 VLM，并发对所有提取出的图片进行重构
        semaphore = asyncio.Semaphore(2)
        async def sem_reconstruct(placeholder, info):
            async with semaphore:
                reconstructed = await reconstruct_image_vlm(
                    client, 
                    abs_path=info["abs_path"], 
                    ext=info["ext"], 
                    model=model, 
                    keep_original=keep_original_images,
                    rel_url=info["url"]
                )
                return placeholder, reconstructed
                
        vlm_tasks = [sem_reconstruct(ph, info) for ph, info in image_dict.items()]
        vlm_results = await asyncio.gather(*vlm_tasks)
        
        for placeholder, reconstructed in vlm_results:
            cleaned_md = cleaned_md.replace(placeholder, reconstructed)
    else:
        # 如果未开启 VLM，直接将原图片链接还原
        for placeholder, info in image_dict.items():
            cleaned_md = cleaned_md.replace(placeholder, info["full_match"])

    return cleaned_md
