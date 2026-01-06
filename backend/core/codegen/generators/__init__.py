# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Generators package for the Executable Workflow Exporter.

This package contains modular code generators for creating standalone
workflow packages from LangConfig workflow configurations.
"""

from .nodes import NodeGenerators
from .tools import ToolGenerators
from .custom_tools import CustomToolGenerators
from .routing import RoutingGenerators
from .templates import TemplateGenerators
from .streamlit_app import StreamlitAppGenerator
from .api_server import ApiServerGenerator

# Conditionally import configurable generator (private/unreleased)
try:
    from .streamlit_configurable import ConfigurableStreamlitGenerator
    CONFIGURABLE_AVAILABLE = True
except ImportError:
    ConfigurableStreamlitGenerator = None  # type: ignore
    CONFIGURABLE_AVAILABLE = False

__all__ = [
    "NodeGenerators",
    "ToolGenerators",
    "CustomToolGenerators",
    "RoutingGenerators",
    "TemplateGenerators",
    "StreamlitAppGenerator",
    "ApiServerGenerator",
    "ConfigurableStreamlitGenerator",
    "CONFIGURABLE_AVAILABLE",
]
