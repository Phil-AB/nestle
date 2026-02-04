"""
Population Agent Infrastructure.

Intelligent agents for PDF form population using LangChain.

Key Components:
- BasePopulationAgent: Abstract base for all population agents
- PopulationAgent: Main LangChain agent for intelligent form population
- Tools: LangChain tools for vision, database, mapping, validation

Design:
- 100% independent (no dependency on other modules)
- Uses shared providers (shared/providers/)
- Follows extraction module's agent pattern
"""

from modules.population.agents.base_population_agent import BasePopulationAgent
from modules.population.agents.population_agent import PopulationAgent

__all__ = [
    "BasePopulationAgent",
    "PopulationAgent",
]
