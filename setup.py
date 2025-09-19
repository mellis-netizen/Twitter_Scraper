#!/usr/bin/env python3
"""
Setup script for Crypto TGE Monitor
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path


def run_command(command, description):
    """Run a command and handle errors."""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e.stderr}")
        return False


def check_python_version():
    """Check if Python version is compatible."""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        return False
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")
    return True


def install_dependencies():
    """Install required dependencies."""
    if not os.path.exists('requirements.txt'):
        print("❌ requirements.txt not found")
        return False
    
    return run_command(
        f"{sys.executable} -m pip install -r requirements.txt",
        "Installing dependencies"
    )


def setup_environment():
    """Setup environment file."""
    env_file = Path('.env')
    env_template = Path('env.template')
    
    if env_file.exists():
        print("✅ .env file already exists")
        return True
    
    if not env_template.exists():
        print("❌ env.template not found")
        return False
    
    try:
        shutil.copy(env_template, env_file)
        print("✅ Created .env file from template")
        print("⚠️  Please edit .env file with your configuration")
        return True
    except Exception as e:
        print(f"❌ Failed to create .env file: {e}")
        return False


def create_directories():
    """Create necessary directories."""
    directories = ['logs']
    
    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
            print(f"✅ Created directory: {directory}")
        except Exception as e:
            print(f"❌ Failed to create directory {directory}: {e}")
            return False
    
    return True


def download_nltk_data():
    """Download required NLTK data."""
    print("🔄 Downloading NLTK data...")
    try:
        import nltk
        nltk.download('punkt', quiet=True)
        print("✅ NLTK data downloaded")
        return True
    except Exception as e:
        print(f"❌ Failed to download NLTK data: {e}")
        return False


def test_installation():
    """Test the installation."""
    print("🔄 Testing installation...")
    
    try:
        # Test imports
        from src.news_scraper import NewsScraper
        from src.twitter_monitor import TwitterMonitor
        from src.email_notifier import EmailNotifier
        from src.main import CryptoTGEMonitor
        
        print("✅ All modules imported successfully")
        
        # Test basic functionality
        monitor = CryptoTGEMonitor()
        print("✅ Monitor instance created successfully")
        
        return True
    except Exception as e:
        print(f"❌ Installation test failed: {e}")
        return False


def main():
    """Main setup function."""
    print("🚀 Crypto TGE Monitor Setup")
    print("=" * 40)
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Create directories
    if not create_directories():
        sys.exit(1)
    
    # Install dependencies
    if not install_dependencies():
        sys.exit(1)
    
    # Download NLTK data
    if not download_nltk_data():
        sys.exit(1)
    
    # Setup environment
    if not setup_environment():
        sys.exit(1)
    
    # Test installation
    if not test_installation():
        sys.exit(1)
    
    print("\n" + "=" * 40)
    print("🎉 Setup completed successfully!")
    print("\nNext steps:")
    print("1. Edit .env file with your configuration")
    print("2. Run: python src/main.py --mode test")
    print("3. Run: python src/main.py --mode once")
    print("4. Run: python src/main.py --mode continuous")
    print("\nFor more information, see README.md")


if __name__ == "__main__":
    main()
