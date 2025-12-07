import logging
import uuid
import threading
import json
import os
from datetime import datetime
from typing import Optional, Any, Dict, List
from functools import wraps
import time

_trace_id_storage = threading.local()
_request_tracer_storage = threading.local()

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
    
    # Add token usage summary if available
    if 'token_usage' in summary_data:
        token_usage = summary_data['token_usage']
        summary_lines.append("Token Usage (Session Total):")
        summary_lines.append(f"  - Input Tokens: {token_usage.get('total_input_tokens', 0)}")
        summary_lines.append(f"  - Output Tokens: {token_usage.get('total_output_tokens', 0)}")
        summary_lines.append(f"  - Total Tokens: {token_usage.get('total_tokens', 0)}")
    
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


class RequestTracer:
    
    TRACES_DIR = "traces"
    
    def __init__(self, trace_id: Optional[str] = None, endpoint: str = "unknown"):
        self.trace_id = trace_id or get_trace_id()
        self.endpoint = endpoint
        self.start_time = datetime.now()
        self.start_timestamp = time.time()
        self.steps: List[Dict[str, Any]] = []
        self.api_calls: List[Dict[str, Any]] = []
        self.errors: List[Dict[str, Any]] = []
        self.metadata: Dict[str, Any] = {
            "trace_id": self.trace_id,
            "endpoint": endpoint,
            "start_time": self.start_time.isoformat(),
        }
        self._current_step: Optional[Dict[str, Any]] = None
        self._step_start_time: Optional[float] = None
        
        os.makedirs(self.TRACES_DIR, exist_ok=True)
    
    def start_step(self, step_name: str, input_data: Optional[Any] = None):
        if self._current_step:
            self.end_step()
        
        self._step_start_time = time.time()
        self._current_step = {
            "step_name": step_name,
            "step_number": len(self.steps) + 1,
            "start_time": datetime.now().isoformat(),
            "input": self._safe_serialize(input_data),
            "output": None,
            "duration_seconds": 0,
            "status": "in_progress",
            "sub_steps": [],
            "api_calls": []
        }
    
    def add_sub_step(self, sub_step_name: str, data: Any = None):
        if self._current_step:
            self._current_step["sub_steps"].append({
                "name": sub_step_name,
                "timestamp": datetime.now().isoformat(),
                "data": self._safe_serialize(data)
            })
    
    def end_step(self, output_data: Any = None, status: str = "success", error: Optional[str] = None):
        if not self._current_step:
            return
        
        self._current_step["end_time"] = datetime.now().isoformat()
        self._current_step["duration_seconds"] = round(time.time() - self._step_start_time, 3) if self._step_start_time else 0
        self._current_step["output"] = self._safe_serialize(output_data)
        self._current_step["status"] = status
        if error:
            self._current_step["error"] = error
        
        self.steps.append(self._current_step)
        self._current_step = None
        self._step_start_time = None
    
    def record_api_call(self, service: str, method: str, endpoint: str = "", 
                        request_data: Any = None, response_data: Any = None,
                        status_code: Optional[int] = None, duration: Optional[float] = None,
                        error: Optional[str] = None):
        token_usage = None
        if isinstance(response_data, dict) and "token_usage" in response_data:
            token_usage = response_data.get("token_usage")
        
        api_call = {
            "service": service,
            "method": method,
            "endpoint": endpoint,
            "timestamp": datetime.now().isoformat(),
            "request": self._safe_serialize(request_data, max_length=2000),
            "response": self._safe_serialize(response_data, max_length=5000),
            "status_code": status_code,
            "duration_seconds": round(duration, 3) if duration else None,
            "error": error,
            "token_usage": token_usage
        }
        
        self.api_calls.append(api_call)
        
        if self._current_step:
            self._current_step["api_calls"].append({
                "service": service,
                "method": method,
                "duration": round(duration, 3) if duration else None,
                "status": "error" if error else "success"
            })
    
    def record_error(self, error_type: str, message: str, details: Any = None, step_name: Optional[str] = None):
        self.errors.append({
            "error_type": error_type,
            "message": message,
            "details": self._safe_serialize(details),
            "step_name": step_name or (self._current_step["step_name"] if self._current_step else None),
            "timestamp": datetime.now().isoformat()
        })
    
    def set_metadata(self, key: str, value: Any):
        self.metadata[key] = self._safe_serialize(value)
    
    def _safe_serialize(self, data: Any, max_length: int = 10000) -> Any:
        if data is None:
            return None
        
        try:
            if isinstance(data, bytes):
                return f"<bytes: {len(data)} bytes>"
            
            if isinstance(data, str):
                if len(data) > max_length:
                    return f"{data[:max_length]}... <truncated: {len(data)} total chars>"
                return data
            
            if isinstance(data, (int, float, bool)):
                return data
            
            if isinstance(data, (list, tuple)):
                if len(data) > 100:
                    return {
                        "_type": "list",
                        "_length": len(data),
                        "_sample": [self._safe_serialize(item, max_length=500) for item in data[:10]],
                        "_note": f"Showing first 10 of {len(data)} items"
                    }
                return [self._safe_serialize(item, max_length=1000) for item in data]
            
            if isinstance(data, dict):
                result = {}
                for k, v in data.items():
                    key_str = str(k)
                    if any(secret in key_str.lower() for secret in ['password', 'secret', 'api_key', 'token', 'auth']):
                        result[key_str] = "****REDACTED****"
                    else:
                        result[key_str] = self._safe_serialize(v, max_length=1000)
                return result
            
            if hasattr(data, '__dict__'):
                return {
                    "_type": type(data).__name__,
                    "_attrs": self._safe_serialize(data.__dict__, max_length=1000)
                }
            
            str_repr = str(data)
            if len(str_repr) > max_length:
                return f"{str_repr[:max_length]}... <truncated>"
            return str_repr
            
        except Exception as e:
            return f"<serialization_error: {str(e)}>"
    
    def get_trace(self) -> Dict[str, Any]:
        if self._current_step:
            self.end_step(status="incomplete")
        
        total_duration = round(time.time() - self.start_timestamp, 3)
        
        total_input_tokens = 0
        total_output_tokens = 0
        total_tokens = 0
        for call in self.api_calls:
            if call.get("token_usage"):
                total_input_tokens += call["token_usage"].get("input_tokens", 0) or 0
                total_output_tokens += call["token_usage"].get("output_tokens", 0) or 0
                total_tokens += call["token_usage"].get("total_tokens", 0) or 0
        
        return {
            "trace_id": self.trace_id,
            "metadata": self.metadata,
            "summary": {
                "total_duration_seconds": total_duration,
                "total_steps": len(self.steps),
                "total_api_calls": len(self.api_calls),
                "total_errors": len(self.errors),
                "status": "error" if self.errors else "success",
                "token_usage": {
                    "total_input_tokens": total_input_tokens,
                    "total_output_tokens": total_output_tokens,
                    "total_tokens": total_tokens
                }
            },
            "steps": self.steps,
            "api_calls": self.api_calls,
            "errors": self.errors,
            "end_time": datetime.now().isoformat()
        }
    
    def save_trace(self) -> str:
        trace_data = self.get_trace()
        
        timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")
        filename = f"trace_{self.trace_id}_{timestamp}.json"
        filepath = os.path.join(self.TRACES_DIR, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(trace_data, f, ensure_ascii=False, indent=2)
        
        return filepath


def get_request_tracer() -> Optional[RequestTracer]:
    return getattr(_request_tracer_storage, 'tracer', None)


def set_request_tracer(tracer: RequestTracer):
    _request_tracer_storage.tracer = tracer


def clear_request_tracer():
    if hasattr(_request_tracer_storage, 'tracer'):
        delattr(_request_tracer_storage, 'tracer')


def trace_step(step_name: str):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            tracer = get_request_tracer()
            
            if tracer:
                input_summary = {
                    "args_count": len(args),
                    "kwargs_keys": list(kwargs.keys())
                }
                tracer.start_step(step_name, input_summary)
            
            try:
                result = func(*args, **kwargs)
                
                if tracer:
                    tracer.end_step(output_data=result, status="success")
                
                return result
                
            except Exception as e:
                if tracer:
                    tracer.record_error("exception", str(e), step_name=step_name)
                    tracer.end_step(status="error", error=str(e))
                raise
        
        return wrapper
    return decorator


def trace_api_call(service: str, method: str):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            tracer = get_request_tracer()
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                if tracer:
                    tracer.record_api_call(
                        service=service,
                        method=method,
                        request_data={"args_count": len(args), "kwargs_keys": list(kwargs.keys())},
                        response_data=result,
                        duration=duration
                    )
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                
                if tracer:
                    tracer.record_api_call(
                        service=service,
                        method=method,
                        request_data={"args_count": len(args), "kwargs_keys": list(kwargs.keys())},
                        error=str(e),
                        duration=duration
                    )
                raise
        
        return wrapper
    return decorator
