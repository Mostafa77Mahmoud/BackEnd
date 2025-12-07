import logging
import uuid
import threading
from typing import Optional
from functools import wraps
import time

_trace_id_storage = threading.local()

_configured_loggers = set()

SERVICE_TAGS = {
    'app.services.database': 'DATABASE',
    'app.services.cloudinary_service': 'CLOUDINARY',
    'app.services.file_search': 'FILE_SEARCH',
    'app.services.ai_service': 'AI_SERVICE',
    'app.routes': 'ROUTE',
    'app.routes.analysis_upload': 'ROUTE',
    'app.routes.analysis_session': 'ROUTE',
    'app.routes.analysis_terms': 'ROUTE',
    'app.routes.file_search': 'ROUTE',
    'app.routes.generation': 'ROUTE',
    'app.routes.interaction': 'ROUTE',
    'app.routes.admin': 'ROUTE',
    'app.routes.root': 'ROUTE',
}


def get_trace_id() -> str:
    trace_id = getattr(_trace_id_storage, 'trace_id', None)
    if trace_id is None:
        trace_id = str(uuid.uuid4())[:8]
        _trace_id_storage.trace_id = trace_id
    return trace_id


def set_trace_id(trace_id: Optional[str] = None) -> str:
    if trace_id is None:
        trace_id = str(uuid.uuid4())[:8]
    _trace_id_storage.trace_id = trace_id
    return trace_id


def clear_trace_id():
    if hasattr(_trace_id_storage, 'trace_id'):
        delattr(_trace_id_storage, 'trace_id')


def mask_key(key: str) -> str:
    if not key:
        return "None"
    if len(key) <= 4:
        return "****"
    return f"****{key[-4:]}"


class TraceIdFormatter(logging.Formatter):
    
    def format(self, record):
        trace_id = get_trace_id()
        
        tag = 'SYSTEM'
        for module_prefix, module_tag in SERVICE_TAGS.items():
            if record.name.startswith(module_prefix):
                tag = module_tag
                break
        
        record.trace_id = trace_id
        record.service_tag = tag
        return super().format(record)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    
    if name in _configured_loggers:
        return logger
    
    logger.handlers.clear()
    
    logger.propagate = False
    
    handler = logging.StreamHandler()
    formatter = TraceIdFormatter(
        '[%(asctime)s] [%(levelname)s] [%(service_tag)s] [%(trace_id)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    
    _configured_loggers.add(name)
    
    return logger


class RequestTimer:
    
    def __init__(self):
        self.start_time = time.time()
        self.steps = {}
        self.current_step = None
        self.step_start = None
    
    def start_step(self, step_name: str):
        if self.current_step and self.step_start:
            self.steps[self.current_step] = time.time() - self.step_start
        self.current_step = step_name
        self.step_start = time.time()
    
    def end_step(self):
        if self.current_step and self.step_start:
            self.steps[self.current_step] = time.time() - self.step_start
            self.current_step = None
            self.step_start = None
    
    def get_step_time(self, step_name: str) -> float:
        return self.steps.get(step_name, 0.0)
    
    def get_total_time(self) -> float:
        return time.time() - self.start_time
    
    def get_summary(self) -> dict:
        if self.current_step and self.step_start:
            self.steps[self.current_step] = time.time() - self.step_start
        
        return {
            "total_time_seconds": round(self.get_total_time(), 2),
            "steps": {k: round(v, 2) for k, v in self.steps.items()}
        }


def log_request_summary(logger: logging.Logger, summary_data: dict):
    summary_lines = [
        "=" * 50,
        "REQUEST SUMMARY",
        "=" * 50,
        f"Trace ID: {summary_data.get('trace_id', 'N/A')}",
        f"File Size: {summary_data.get('file_size', 'N/A')} bytes",
        f"Extracted Characters: {summary_data.get('extracted_chars', 'N/A')}",
        f"Analysis Status: {summary_data.get('analysis_status', 'N/A')}",
        f"File Search Status: {summary_data.get('file_search_status', 'N/A')}",
        f"Total Time: {summary_data.get('total_time', 'N/A')} seconds",
    ]
    
    if 'step_times' in summary_data:
        summary_lines.append("Step Times:")
        for step, time_val in summary_data['step_times'].items():
            summary_lines.append(f"  - {step}: {time_val}s")
    
    summary_lines.append("=" * 50)
    
    for line in summary_lines:
        logger.info(line)


def create_error_response(error_type: str, message: str, details: Optional[dict] = None) -> dict:
    return {
        "status": "error",
        "error_type": error_type,
        "message": message,
        "details": details or {},
        "trace_id": get_trace_id()
    }


def create_success_response(data: dict, message: str = "Operation completed successfully") -> dict:
    return {
        "status": "success",
        "message": message,
        "data": data,
        "trace_id": get_trace_id()
    }
