"""JSON-to-Python Class Converter
An agentic AI tool that converts raw JSON to Python Dataclasses and Pydantic v2 models.
"""

from json2py.agent.loop import AgentConverter, ConversionResult
from json2py.models import OutputFormat

__version__ = "1.0.0"
__all__ = ["AgentConverter", "ConversionResult", "OutputFormat"]
