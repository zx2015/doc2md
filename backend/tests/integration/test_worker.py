import pytest
import sys
import os
from unittest.mock import MagicMock

sys.modules['torch'] = MagicMock()
sys.modules['docling'] = MagicMock()
sys.modules['docling.document_converter'] = MagicMock()
sys.modules['docling.datamodel'] = MagicMock()
sys.modules['docling.datamodel.pipeline_options'] = MagicMock()
sys.modules['docling.datamodel.base_models'] = MagicMock()
sys.modules['docling_core'] = MagicMock()
sys.modules['docling_core.transforms'] = MagicMock()
sys.modules['docling_core.transforms.chunker'] = MagicMock()
sys.modules['docling_core.transforms.chunker.hybrid_chunker'] = MagicMock()
sys.modules['docling_core.types'] = MagicMock()
sys.modules['docling_core.types.doc'] = MagicMock()
sys.modules['docling_core.types.doc.document'] = MagicMock()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.worker.tasks import convert_task

# Add a simple mock test since actual Celery integration needs real Torch and DB
def test_convert_task_mock():
    # As an integration test placeholder, we would normally use celery_app.Task.apply
    pass
