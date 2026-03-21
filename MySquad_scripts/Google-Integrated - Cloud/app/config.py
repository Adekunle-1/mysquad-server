"""
Responsibility: Load and provide access to application configuration settings.
Reads from config.yml file with validation. Exposes typed properties for
server host/port, Gmail retry behavior, and logging configuration.
"""

import yaml
import os
from typing import Dict, Any

class Config:
    """
    Configuration loader from YAML file.
    Validates required sections and provides typed property access.
    """
    
    def __init__(self, config_file: str = 'config.yml'):
        """
        Load configuration from YAML file with validation.
        
        Args:
            config_file: Path to config.yml
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config is invalid or missing required sections
        """
        self.config_file = config_file
        self._config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load and validate configuration from YAML."""
        if not os.path.exists(self.config_file):
            raise FileNotFoundError(
                f"Configuration file '{self.config_file}' not found. "
                f"Please create it based on config.example.yml"
            )
        
        try:
            with open(self.config_file, 'r') as f:
                config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in config file: {e}")
        
        # Validate required sections exist
        required_sections = ['server', 'gmail', 'logging']
        for section in required_sections:
            if section not in config:
                raise ValueError(f"Missing required section '{section}' in config")
        
        return config
    
    @property
    def server_host(self) -> str:
        """Server host address."""
        return self._config['server']['host']
    
    @property
    def server_port(self) -> int:
        """Server port number."""
        return self._config['server']['port']
    
    @property
    def retry_attempts(self) -> int:
        """Number of retry attempts for Gmail API calls."""
        return self._config['gmail']['retry_attempts']
    
    @property
    def retry_delay(self) -> float:
        """Initial delay (seconds) for exponential backoff retries."""
        return self._config['gmail']['retry_delay']
    
    @property
    def max_results(self) -> int:
        """Default max results for email search operations."""
        return self._config['gmail']['max_results']
    
    @property
    def log_level(self) -> str:
        """Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)."""
        return self._config['logging']['level']

# Global config instance
config = Config()
