#!/usr/bin/env python3
"""
Unit tests for Configuration Manager
Tests configuration persistence, validation, and observer pattern
"""

import unittest
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from config_manager import ApplicationConfiguration, ConfigSchema


class TestConfigSchema(unittest.TestCase):
    """Test cases for ConfigSchema validation"""
    
    def test_default_config_creation(self):
        """Test creation with default values"""
        config = ConfigSchema()
        
        # Check defaults
        self.assertEqual(config.analysis_retention_days, 10)
        self.assertEqual(config.analysis_hourly_rate, 250.0)
        self.assertEqual(config.analysis_inactivity_threshold, 60)
        self.assertEqual(config.performance_thread_pool_size, 4)
        self.assertEqual(config.ui_default_theme, 'light')
        self.assertEqual(config.ui_language, 'cs')
    
    def test_config_validation_valid(self):
        """Test validation with valid values"""
        config = ConfigSchema(
            analysis_retention_days=30,
            analysis_hourly_rate=500.0,
            performance_thread_pool_size=8,
            ui_default_theme='dark'
        )
        
        errors = config.validate()
        self.assertEqual(len(errors), 0)
    
    def test_config_validation_invalid_retention(self):
        """Test validation with invalid retention days"""
        # Too low
        config = ConfigSchema(analysis_retention_days=0)
        errors = config.validate()
        self.assertIn("analysis_retention_days musí být mezi 1 a 365", errors)
        
        # Too high
        config = ConfigSchema(analysis_retention_days=400)
        errors = config.validate()
        self.assertIn("analysis_retention_days musí být mezi 1 a 365", errors)
    
    def test_config_validation_invalid_rate(self):
        """Test validation with invalid hourly rate"""
        config = ConfigSchema(analysis_hourly_rate=-100)
        errors = config.validate()
        self.assertIn("analysis_hourly_rate nemůže být záporná", errors)
    
    def test_config_validation_invalid_threshold(self):
        """Test validation with invalid inactivity threshold"""
        config = ConfigSchema(analysis_inactivity_threshold=5)
        errors = config.validate()
        self.assertIn("analysis_inactivity_threshold musí být mezi 10 a 3600", errors)
    
    def test_config_validation_invalid_threads(self):
        """Test validation with invalid thread pool size"""
        config = ConfigSchema(performance_thread_pool_size=20)
        errors = config.validate()
        self.assertIn("performance_thread_pool_size musí být mezi 1 a 16", errors)
    
    def test_config_validation_invalid_theme(self):
        """Test validation with invalid theme"""
        config = ConfigSchema(ui_default_theme='blue')
        errors = config.validate()
        self.assertIn("ui_default_theme musí být 'light' nebo 'dark'", errors)
    
    def test_config_validation_invalid_language(self):
        """Test validation with invalid language"""
        config = ConfigSchema(ui_language='fr')
        errors = config.validate()
        self.assertIn("ui_language musí být 'cs' nebo 'en'", errors)


class TestApplicationConfiguration(unittest.TestCase):
    """Test cases for ApplicationConfiguration"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create temporary directory for test configs
        self.test_dir = tempfile.mkdtemp()
        self.config_path = Path(self.test_dir) / "test_config.json"
    
    def tearDown(self):
        """Clean up test fixtures"""
        # Remove temporary directory
        shutil.rmtree(self.test_dir)
    
    def test_create_new_config(self):
        """Test creation of new configuration"""
        config = ApplicationConfiguration(
            config_path=self.config_path,
            auto_save=True
        )
        
        # Should create config file
        self.assertTrue(self.config_path.exists())
        
        # Should have default values
        self.assertEqual(config.get('analysis.retention_days'), 10)
        self.assertEqual(config.get('ui.default_theme'), 'light')
    
    def test_load_existing_config(self):
        """Test loading existing configuration"""
        # Create config file
        test_config = {
            '_version': '1.0',
            'analysis_retention_days': 20,
            'analysis_hourly_rate': 300.0,
            'ui_default_theme': 'dark'
        }
        
        with open(self.config_path, 'w') as f:
            json.dump(test_config, f)
        
        # Load config
        config = ApplicationConfiguration(config_path=self.config_path)
        
        self.assertEqual(config.get('analysis.retention_days'), 20)
        self.assertEqual(config.get('analysis.hourly_rate'), 300.0)
        self.assertEqual(config.get('ui.default_theme'), 'dark')
    
    def test_get_with_default(self):
        """Test getting values with default"""
        config = ApplicationConfiguration(config_path=self.config_path)
        
        # Existing key
        self.assertEqual(config.get('analysis.retention_days', 999), 10)
        
        # Non-existing key
        self.assertEqual(config.get('nonexistent.key', 'default'), 'default')
    
    def test_set_value(self):
        """Test setting configuration values"""
        config = ApplicationConfiguration(
            config_path=self.config_path,
            auto_save=True
        )
        
        # Set valid value
        success = config.set('analysis.hourly_rate', 400.0)
        self.assertTrue(success)
        self.assertEqual(config.get('analysis.hourly_rate'), 400.0)
        
        # Verify saved to file
        with open(self.config_path, 'r') as f:
            saved_data = json.load(f)
        self.assertEqual(saved_data['analysis_hourly_rate'], 400.0)
    
    def test_set_invalid_value(self):
        """Test setting invalid values"""
        config = ApplicationConfiguration(config_path=self.config_path)
        
        # Set invalid value (negative rate)
        success = config.set('analysis.hourly_rate', -100)
        self.assertFalse(success)
        
        # Value should not change
        self.assertNotEqual(config.get('analysis.hourly_rate'), -100)
    
    def test_set_unknown_key(self):
        """Test setting unknown configuration key"""
        config = ApplicationConfiguration(config_path=self.config_path)
        
        success = config.set('unknown.key', 'value')
        self.assertFalse(success)
    
    def test_batch_update(self):
        """Test batch update functionality"""
        config = ApplicationConfiguration(config_path=self.config_path)
        
        updates = {
            'analysis.retention_days': 15,
            'performance.thread_pool_size': 6,
            'ui.refresh_interval': 2000
        }
        
        success = config.update(updates)
        self.assertTrue(success)
        
        # Verify all values updated
        self.assertEqual(config.get('analysis.retention_days'), 15)
        self.assertEqual(config.get('performance.thread_pool_size'), 6)
        self.assertEqual(config.get('ui.refresh_interval'), 2000)
    
    def test_batch_update_rollback(self):
        """Test rollback on batch update failure"""
        config = ApplicationConfiguration(config_path=self.config_path)
        
        original_rate = config.get('analysis.hourly_rate')
        
        updates = {
            'analysis.hourly_rate': 500.0,  # Valid
            'analysis.retention_days': 1000  # Invalid - too high
        }
        
        success = config.update(updates)
        self.assertFalse(success)
        
        # Should rollback all changes
        self.assertEqual(config.get('analysis.hourly_rate'), original_rate)
    
    def test_reset_to_defaults(self):
        """Test resetting to default values"""
        config = ApplicationConfiguration(config_path=self.config_path)
        
        # Change some values
        config.set('analysis.hourly_rate', 500.0)
        config.set('ui.default_theme', 'dark')
        
        # Reset specific key
        config.reset_to_defaults('analysis.hourly_rate')
        self.assertEqual(config.get('analysis.hourly_rate'), 250.0)
        self.assertEqual(config.get('ui.default_theme'), 'dark')  # Unchanged
        
        # Reset all
        config.reset_to_defaults()
        self.assertEqual(config.get('ui.default_theme'), 'light')
    
    def test_observer_pattern(self):
        """Test observer notifications"""
        config = ApplicationConfiguration(config_path=self.config_path)
        
        changes = []
        
        def observer(key_path, old_value, new_value):
            changes.append({
                'key': key_path,
                'old': old_value,
                'new': new_value
            })
        
        config.register_observer(observer)
        
        # Make changes
        config.set('analysis.hourly_rate', 300.0)
        
        # Verify notification
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]['key'], 'analysis.hourly_rate')
        self.assertEqual(changes[0]['old'], 250.0)
        self.assertEqual(changes[0]['new'], 300.0)
        
        # Unregister observer
        config.unregister_observer(observer)
        config.set('analysis.hourly_rate', 350.0)
        
        # Should not receive new notifications
        self.assertEqual(len(changes), 1)
    
    def test_observer_exception_handling(self):
        """Test handling of exceptions in observers"""
        config = ApplicationConfiguration(config_path=self.config_path)
        
        def failing_observer(key_path, old_value, new_value):
            raise RuntimeError("Observer error")
        
        config.register_observer(failing_observer)
        
        # Should not crash when observer fails
        success = config.set('analysis.hourly_rate', 300.0)
        self.assertTrue(success)
        self.assertEqual(config.get('analysis.hourly_rate'), 300.0)
    
    def test_export_import_config(self):
        """Test configuration export and import"""
        config = ApplicationConfiguration(config_path=self.config_path)
        
        # Modify config
        config.set('analysis.retention_days', 20)
        config.set('ui.default_theme', 'dark')
        
        # Export
        export_path = Path(self.test_dir) / "export.json"
        success = config.export_config(export_path)
        self.assertTrue(success)
        self.assertTrue(export_path.exists())
        
        # Create new config instance
        config2 = ApplicationConfiguration(
            config_path=Path(self.test_dir) / "config2.json"
        )
        
        # Import
        success = config2.import_config(export_path)
        self.assertTrue(success)
        
        # Verify imported values
        self.assertEqual(config2.get('analysis.retention_days'), 20)
        self.assertEqual(config2.get('ui.default_theme'), 'dark')
    
    def test_import_invalid_config(self):
        """Test importing invalid configuration"""
        config = ApplicationConfiguration(config_path=self.config_path)
        
        # Create invalid config
        invalid_config = {
            'analysis_retention_days': 1000,  # Too high
            'ui_default_theme': 'invalid'
        }
        
        invalid_path = Path(self.test_dir) / "invalid.json"
        with open(invalid_path, 'w') as f:
            json.dump(invalid_config, f)
        
        # Import should fail
        original_retention = config.get('analysis.retention_days')
        success = config.import_config(invalid_path)
        self.assertFalse(success)
        
        # Config should remain unchanged
        self.assertEqual(config.get('analysis.retention_days'), original_retention)
    
    def test_change_history(self):
        """Test configuration change history"""
        config = ApplicationConfiguration(config_path=self.config_path)
        
        # Make some changes
        config.set('analysis.hourly_rate', 300.0)
        config.set('ui.default_theme', 'dark')
        config.set('analysis.hourly_rate', 350.0)  # Change again
        
        # Get history
        history = config.get_change_history()
        self.assertEqual(len(history), 3)
        
        # Verify history entries
        self.assertEqual(history[0]['key'], 'analysis.hourly_rate')
        self.assertEqual(history[0]['old_value'], 250.0)
        self.assertEqual(history[0]['new_value'], 300.0)
        
        # Get limited history
        limited = config.get_change_history(limit=2)
        self.assertEqual(len(limited), 2)
        
        # Clear history
        config.clear_change_history()
        history = config.get_change_history()
        self.assertEqual(len(history), 0)
    
    def test_directory_creation(self):
        """Test automatic directory creation"""
        config = ApplicationConfiguration(config_path=self.config_path)
        
        # Check default directories were created
        data_dir = Path(config.config.paths_data_dir)
        log_dir = Path(config.config.paths_log_dir)
        export_dir = Path(config.config.paths_export_dir)
        
        self.assertTrue(data_dir.exists())
        self.assertTrue(log_dir.exists())
        self.assertTrue(export_dir.exists())
    
    def test_auto_save_disabled(self):
        """Test behavior with auto-save disabled"""
        config = ApplicationConfiguration(
            config_path=self.config_path,
            auto_save=False
        )
        
        # Make change
        config.set('analysis.hourly_rate', 300.0)
        
        # Should not save to file
        with open(self.config_path, 'r') as f:
            saved_data = json.load(f)
        self.assertEqual(saved_data['analysis_hourly_rate'], 250.0)  # Still default
    
    def test_config_as_dict(self):
        """Test getting configuration as dictionary"""
        config = ApplicationConfiguration(config_path=self.config_path)
        
        config_dict = config.as_dict()
        
        self.assertIsInstance(config_dict, dict)
        self.assertEqual(config_dict['analysis_retention_days'], 10)
        self.assertEqual(config_dict['ui_default_theme'], 'light')
    
    def test_config_string_representation(self):
        """Test string representation of config"""
        config = ApplicationConfiguration(config_path=self.config_path)
        
        config_str = str(config)
        
        self.assertIsInstance(config_str, str)
        # Should be valid JSON
        parsed = json.loads(config_str)
        self.assertEqual(parsed['analysis_retention_days'], 10)
    
    def test_corrupt_config_handling(self):
        """Test handling of corrupted config files"""
        # Write invalid JSON
        with open(self.config_path, 'w') as f:
            f.write("{ invalid json")
        
        # Should fall back to defaults
        config = ApplicationConfiguration(config_path=self.config_path)
        self.assertEqual(config.get('analysis.retention_days'), 10)
    
    def test_version_migration(self):
        """Test configuration version migration"""
        # Create old version config
        old_config = {
            '_version': '0.9',
            'analysis_retention_days': 15
        }
        
        with open(self.config_path, 'w') as f:
            json.dump(old_config, f)
        
        # Load should trigger migration
        with patch.object(ApplicationConfiguration, '_migrate_config') as mock_migrate:
            mock_migrate.return_value = old_config
            config = ApplicationConfiguration(config_path=self.config_path)
            
            # Verify migration was called
            mock_migrate.assert_called_once_with(old_config, '0.9')
    
    def test_concurrent_access_safety(self):
        """Test thread-safe configuration access"""
        import threading
        
        config = ApplicationConfiguration(config_path=self.config_path)
        
        results = []
        errors = []
        
        def modify_config(value):
            try:
                for _ in range(10):
                    config.set('analysis.hourly_rate', value)
                    result = config.get('analysis.hourly_rate')
                    results.append(result)
            except Exception as e:
                errors.append(e)
        
        # Start multiple threads
        threads = []
        for i in range(5):
            t = threading.Thread(target=modify_config, args=(100 + i * 50,))
            t.start()
            threads.append(t)
        
        # Wait for completion
        for t in threads:
            t.join()
        
        # Should have no errors
        self.assertEqual(len(errors), 0)
        # All results should be valid values
        self.assertTrue(all(isinstance(r, (int, float)) for r in results))


class TestConfigSchemaEdgeCases(unittest.TestCase):
    """Test edge cases for ConfigSchema"""
    
    def test_boundary_values(self):
        """Test boundary values for validation"""
        # Test exact boundaries
        config = ConfigSchema(
            analysis_retention_days=1,  # Min
            analysis_inactivity_threshold=10,  # Min
            performance_thread_pool_size=1  # Min
        )
        errors = config.validate()
        self.assertEqual(len(errors), 0)
        
        config = ConfigSchema(
            analysis_retention_days=365,  # Max
            analysis_inactivity_threshold=3600,  # Max
            performance_thread_pool_size=16  # Max
        )
        errors = config.validate()
        self.assertEqual(len(errors), 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)