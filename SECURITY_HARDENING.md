# Production Security Hardening Guide

## Overview

This guide provides comprehensive security hardening procedures for deploying Mac Activity Analyzer in production environments.

## Security Checklist

### 1. Input Validation ✓

All user inputs must be validated before processing:

```python
# Example: File path validation
def validate_file_path(path: str) -> bool:
    """Validate file path for security"""
    try:
        path_obj = Path(path).resolve()
        
        # Prevent path traversal
        if ".." in str(path_obj):
            return False
            
        # Ensure within allowed directories
        allowed_dirs = [
            Path.home() / "Documents",
            Path.home() / "Downloads",
            Path("/tmp")
        ]
        
        return any(path_obj.is_relative_to(allowed) for allowed in allowed_dirs)
    except:
        return False

# Example: Export format validation
ALLOWED_EXPORT_FORMATS = {'json', 'csv', 'html'}

def validate_export_format(format: str) -> bool:
    return format.lower() in ALLOWED_EXPORT_FORMATS
```

### 2. File Size Limits ✓

Implement strict file size limits:

```python
MAX_IMPORT_SIZE = 50 * 1024 * 1024  # 50 MB

def check_file_size(file_path: Path) -> bool:
    """Check if file size is within limits"""
    try:
        size = file_path.stat().st_size
        return size <= MAX_IMPORT_SIZE
    except:
        return False

# Usage in import
def import_logs(file_path: str):
    path = Path(file_path)
    
    if not path.exists():
        raise ValueError("File does not exist")
    
    if not check_file_size(path):
        raise ValueError(f"File too large. Maximum size: {MAX_IMPORT_SIZE/1024/1024}MB")
    
    # Proceed with import...
```

### 3. Rate Limiting

Implement rate limiting for resource-intensive operations:

```python
from collections import defaultdict
from datetime import datetime, timedelta
import threading

class RateLimiter:
    """Rate limiter for operations"""
    
    def __init__(self, max_calls: int, time_window: timedelta):
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = defaultdict(list)
        self.lock = threading.Lock()
    
    def is_allowed(self, key: str) -> bool:
        """Check if operation is allowed"""
        with self.lock:
            now = datetime.now()
            
            # Clean old entries
            self.calls[key] = [
                call_time for call_time in self.calls[key]
                if now - call_time < self.time_window
            ]
            
            # Check limit
            if len(self.calls[key]) >= self.max_calls:
                return False
            
            # Record call
            self.calls[key].append(now)
            return True

# Usage
command_limiter = RateLimiter(
    max_calls=10,
    time_window=timedelta(minutes=1)
)

def execute_command_with_limit(command: str):
    if not command_limiter.is_allowed("command_execution"):
        raise Exception("Rate limit exceeded. Please wait.")
    
    return executor.execute_command(command)
```

### 4. Audit Logging

Implement comprehensive audit logging:

```python
import json
from datetime import datetime
from pathlib import Path

class SecurityAuditLogger:
    """Security audit logger"""
    
    def __init__(self, audit_file: Path):
        self.audit_file = audit_file
        self.audit_file.parent.mkdir(parents=True, exist_ok=True)
    
    def log_security_event(
        self,
        event_type: str,
        user: str,
        action: str,
        resource: str,
        result: str,
        details: dict = None
    ):
        """Log security-relevant event"""
        event = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'user': user,
            'action': action,
            'resource': resource,
            'result': result,
            'details': details or {}
        }
        
        # Append to audit log
        with open(self.audit_file, 'a') as f:
            f.write(json.dumps(event) + '\n')
    
    def log_command_execution(self, user: str, command: str, success: bool):
        """Log command execution"""
        self.log_security_event(
            event_type='COMMAND_EXECUTION',
            user=user,
            action='execute',
            resource=command,
            result='success' if success else 'failure'
        )
    
    def log_file_access(self, user: str, file_path: str, operation: str):
        """Log file access"""
        self.log_security_event(
            event_type='FILE_ACCESS',
            user=user,
            action=operation,
            resource=file_path,
            result='success'
        )
    
    def log_authentication(self, user: str, success: bool, method: str):
        """Log authentication attempt"""
        self.log_security_event(
            event_type='AUTHENTICATION',
            user=user,
            action='login',
            resource=method,
            result='success' if success else 'failure'
        )

# Initialize audit logger
audit_logger = SecurityAuditLogger(
    Path.home() / '.mac_activity_analyzer' / 'audit.log'
)
```

### 5. Secure Session Management

For web-based deployments:

```python
import secrets
import time
from typing import Dict, Optional

class SecureSessionManager:
    """Secure session management"""
    
    def __init__(self, session_timeout: int = 3600):
        self.sessions: Dict[str, dict] = {}
        self.session_timeout = session_timeout
    
    def create_session(self, user_id: str) -> str:
        """Create new secure session"""
        # Generate secure token
        token = secrets.token_urlsafe(32)
        
        # Store session
        self.sessions[token] = {
            'user_id': user_id,
            'created_at': time.time(),
            'last_activity': time.time()
        }
        
        # Log session creation
        audit_logger.log_authentication(user_id, True, 'session_created')
        
        return token
    
    def validate_session(self, token: str) -> Optional[str]:
        """Validate and refresh session"""
        if token not in self.sessions:
            return None
        
        session = self.sessions[token]
        current_time = time.time()
        
        # Check timeout
        if current_time - session['last_activity'] > self.session_timeout:
            self.destroy_session(token)
            return None
        
        # Refresh activity time
        session['last_activity'] = current_time
        
        return session['user_id']
    
    def destroy_session(self, token: str):
        """Destroy session"""
        if token in self.sessions:
            user_id = self.sessions[token]['user_id']
            del self.sessions[token]
            audit_logger.log_authentication(user_id, True, 'session_destroyed')
    
    def cleanup_expired_sessions(self):
        """Remove expired sessions"""
        current_time = time.time()
        expired = [
            token for token, session in self.sessions.items()
            if current_time - session['last_activity'] > self.session_timeout
        ]
        
        for token in expired:
            self.destroy_session(token)
```

### 6. Data Sanitization

Sanitize all data before display or export:

```python
import html
import re

def sanitize_for_html(text: str) -> str:
    """Sanitize text for HTML display"""
    # Escape HTML entities
    text = html.escape(text)
    
    # Remove any remaining suspicious patterns
    text = re.sub(r'<script.*?</script>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)
    
    return text

def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe file operations"""
    # Remove path components
    filename = Path(filename).name
    
    # Remove dangerous characters
    filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    
    # Limit length
    max_length = 255
    if len(filename) > max_length:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        filename = name[:max_length-len(ext)-1] + '.' + ext if ext else name[:max_length]
    
    return filename
```

### 7. Secure Configuration Storage

Encrypt sensitive configuration:

```python
from cryptography.fernet import Fernet
import json
import base64

class SecureConfigStorage:
    """Secure configuration storage with encryption"""
    
    def __init__(self, key_file: Path):
        self.key_file = key_file
        self.cipher = self._get_or_create_cipher()
    
    def _get_or_create_cipher(self) -> Fernet:
        """Get or create encryption cipher"""
        if self.key_file.exists():
            with open(self.key_file, 'rb') as f:
                key = f.read()
        else:
            # Generate new key
            key = Fernet.generate_key()
            self.key_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.key_file, 'wb') as f:
                f.write(key)
            # Set restrictive permissions
            self.key_file.chmod(0o600)
        
        return Fernet(key)
    
    def encrypt_config(self, config: dict) -> str:
        """Encrypt configuration data"""
        json_data = json.dumps(config)
        encrypted = self.cipher.encrypt(json_data.encode())
        return base64.b64encode(encrypted).decode()
    
    def decrypt_config(self, encrypted_data: str) -> dict:
        """Decrypt configuration data"""
        try:
            encrypted = base64.b64decode(encrypted_data.encode())
            decrypted = self.cipher.decrypt(encrypted)
            return json.loads(decrypted.decode())
        except:
            raise ValueError("Failed to decrypt configuration")
```

### 8. Network Security (for API deployments)

```python
import ssl
from http.server import HTTPServer, BaseHTTPRequestHandler

def create_secure_server(host: str, port: int, handler_class):
    """Create HTTPS server with proper SSL configuration"""
    
    # Create SSL context
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    
    # Load certificate
    context.load_cert_chain(
        certfile='server.crt',
        keyfile='server.key'
    )
    
    # Configure SSL
    context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS')
    context.options |= ssl.OP_NO_SSLv2 | ssl.OP_NO_SSLv3 | ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1
    
    # Create server
    server = HTTPServer((host, port), handler_class)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    
    return server
```

### 9. Resource Monitoring

Monitor and limit resource usage:

```python
import psutil
import resource

class ResourceMonitor:
    """Monitor and limit resource usage"""
    
    def __init__(self, max_memory_mb: int = 500, max_cpu_percent: int = 50):
        self.max_memory_mb = max_memory_mb
        self.max_cpu_percent = max_cpu_percent
        self.process = psutil.Process()
    
    def check_resources(self) -> bool:
        """Check if resources are within limits"""
        # Check memory
        memory_mb = self.process.memory_info().rss / 1024 / 1024
        if memory_mb > self.max_memory_mb:
            return False
        
        # Check CPU (average over 1 second)
        cpu_percent = self.process.cpu_percent(interval=1)
        if cpu_percent > self.max_cpu_percent:
            return False
        
        return True
    
    def set_resource_limits(self):
        """Set hard resource limits (Unix only)"""
        try:
            # Set memory limit
            memory_limit = self.max_memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
            
            # Set CPU time limit (optional)
            # resource.setrlimit(resource.RLIMIT_CPU, (300, 300))  # 5 minutes
        except:
            pass  # May not work on all systems

# Usage
monitor = ResourceMonitor(max_memory_mb=1000)

def resource_intensive_operation():
    if not monitor.check_resources():
        raise Exception("Resource limits exceeded")
    
    # Perform operation...
```

### 10. Security Headers (Web Deployment)

```python
class SecurityHeadersMiddleware:
    """Add security headers to responses"""
    
    SECURITY_HEADERS = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline';",
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        'Permissions-Policy': 'geolocation=(), microphone=(), camera=()'
    }
    
    def process_response(self, response):
        """Add security headers to response"""
        for header, value in self.SECURITY_HEADERS.items():
            response.headers[header] = value
        return response
```

## Deployment Security Checklist

- [ ] All dependencies updated to latest secure versions
- [ ] File permissions set correctly (config: 600, logs: 640)
- [ ] Audit logging enabled and monitored
- [ ] Rate limiting configured for all operations
- [ ] Input validation active on all user inputs
- [ ] SSL/TLS configured for network communications
- [ ] Regular security updates scheduled
- [ ] Incident response plan in place
- [ ] Data retention policies configured
- [ ] Access controls implemented

## Security Testing

Run security tests before deployment:

```bash
# Run security-focused tests
python -m pytest test_security.py -v

# Check for known vulnerabilities
pip install safety
safety check

# Static security analysis
pip install bandit
bandit -r . -f json -o security_report.json
```

## Incident Response

In case of security incident:

1. **Immediate Actions**
   - Disable affected components
   - Preserve audit logs
   - Notify security team

2. **Investigation**
   - Review audit logs
   - Identify scope of breach
   - Document timeline

3. **Remediation**
   - Patch vulnerabilities
   - Reset credentials
   - Update security measures

4. **Recovery**
   - Restore from secure backups
   - Verify system integrity
   - Resume operations

5. **Post-Incident**
   - Complete incident report
   - Update security procedures
   - Implement lessons learned