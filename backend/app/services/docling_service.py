import torch
import gc
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import RapidOcrOptions, PdfPipelineOptions, AcceleratorOptions
from docling.datamodel.base_models import InputFormat
from docling_core.types.doc.base import ImageRefMode

def resolve_device(device_setting: str) -> str:
    if device_setting == "cuda":
        return "cuda" if torch.cuda.is_available() else "cpu"
    elif device_setting == "cpu":
        return "cpu"
    # auto
    return "cuda" if torch.cuda.is_available() else "cpu"

def run_docling_conversion(input_path: str, device_setting: str = "auto", progress_callback=None) -> tuple:
    device = resolve_device(device_setting)
    
    # Configure Pipeline
    pipeline_options = PdfPipelineOptions()
    pipeline_options.accelerator_options = AcceleratorOptions(device=device)
    pipeline_options.do_ocr = True
    pipeline_options.ocr_options = RapidOcrOptions()
    pipeline_options.generate_picture_images = True # Patch 12.1: 必须开启提取图片
    pipeline_options.generate_page_images = False
    
    # If progress callback is provided, hook into descriptor
    if progress_callback:
        # Note: Hook into docling progress tracking if API supports it,
        # otherwise simulate based on finished pages.
        pass

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )
    
    try:
        result = converter.convert(input_path)
        doc = result.document
        
        # Export with embedded Base64 images for self-contained single-file Markdown
        markdown_content = doc.export_to_markdown(image_mode=ImageRefMode.EMBEDDED)
        
        # Force PyTorch memory release immediately
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            
        return markdown_content, result
    except Exception as e:
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        raise e
