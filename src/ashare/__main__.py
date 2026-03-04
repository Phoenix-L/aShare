"""Entry point for running the package as a module."""

from ashare.cli import cli
from ashare.utils.logging import setup_logging

# Initialize logging when module is run
setup_logging()

if __name__ == "__main__":
    cli()
