import os
from pathlib import Path

def test_no_obsolete_docling_imports():
    """
    Enforce that no service files import docling or docling_core,
    preventing spec and implementation divergence.
    """
    services_dir = Path(__file__).parent.parent.parent / "app" / "services"
    docling_imports = []
    
    for py_file in services_dir.rglob("*.py"):
        with open(py_file, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                # Check for active imports, ignoring comments
                cleaned_line = line.strip()
                if cleaned_line.startswith("#"):
                    continue
                if "import docling" in cleaned_line or "from docling" in cleaned_line:
                    docling_imports.append(f"{py_file.name}:{line_no}: {cleaned_line}")
                    
    assert not docling_imports, f"Obsolete Docling imports found: {docling_imports}"

def test_spec_alignment():
    """
    Check that the specification document exists and references MinerU.
    """
    spec_path = Path(__file__).parent.parent.parent.parent / "docs" / "superpowers" / "specs" / "2026-06-12-doc2md-design.md"
    assert spec_path.exists(), "Design specification file is missing!"
    
    with open(spec_path, "r", encoding="utf-8") as f:
        spec_content = f.read()
        
    assert "MinerU" in spec_content, "Spec does not refer to MinerU engine"
