import os
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def run_mineru_conversion(pdf_path: str, output_dir: str, timeout: int = 600) -> tuple[str, str]:
    """
    Runs MinerU (MagicDocs) via CLI to extract text, tables, and images from a PDF.
    Returns a tuple of (parsed_markdown_text, real_output_dir).
    """
    logger.info(f"Starting MinerU extraction for {pdf_path}")
    
    try:
        cmd = [
            "/media/data/venv/bin/magic-pdf",
            "-p", pdf_path,
            "-o", output_dir,
            "-m", "auto"
        ]
        
        logger.info(f"Running MinerU CLI: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=timeout)
        logger.info(f"MinerU stdout: {result.stdout}")
        
        # Recursively search for .md output file in output_dir
        md_files = list(Path(output_dir).rglob("*.md"))
        if not md_files:
            raise FileNotFoundError(
                f"No .md produced. output_dir tree:\n" +
                "\n".join(str(p) for p in Path(output_dir).rglob("*"))
            )
            
        # Select the first MD file generated
        md_path = str(md_files[0])
        real_output_dir = os.path.dirname(md_path)
        
        with open(md_path, 'r', encoding='utf-8') as f:
            md_content = f.read()
            
        logger.info(f"MinerU extraction complete. Real output dir: {real_output_dir}")
        return md_content, real_output_dir
        
    except subprocess.CalledProcessError as e:
        logger.error(f"MinerU CLI failed. Stderr: {e.stderr}\nStdout: {e.stdout}", exc_info=True)
        raise RuntimeError(f"MinerU conversion failed: {e.stderr}\nStdout: {e.stdout}")
    except subprocess.TimeoutExpired as e:
        logger.error(f"MinerU CLI timed out after {timeout} seconds", exc_info=True)
        raise RuntimeError(f"MinerU conversion timed out after {timeout} seconds")
    except Exception as e:
        logger.error(f"MinerU extraction failed: {str(e)}", exc_info=True)
        raise RuntimeError(f"MinerU conversion failed: {str(e)}")
