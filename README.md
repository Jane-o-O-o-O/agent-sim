# Agent Sim

Multi-agent simulation framework for testing agent communication, coordination, and evaluation.

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## About

Agent Sim is a multi-agent simulation framework for defining, running, and evaluating communication and coordination scenarios between multiple agents. Suitable for researching and testing interaction patterns, conflict resolution strategies, and overall effectiveness in multi-agent systems.

## Implemented

### Agent Base Class (`agent_sim.agent`)
- `AgentConfig` - Pydantic config model (name, description, max_steps)
- `AgentState` - Runtime state (step_count, status, data)
- `Agent` ABC - Subclasses only need to implement `act()` method
- Lifecycle: `observe()` -> `act()` -> `step()` -> `reset()`
- Automatic inbox management and max_steps completion detection

### Communication Bus (`agent_sim.communication`)
- `Message` - Pydantic message model (sender, receiver, content, topic)
- `MessageBus` - Agent register/unregister, direct/broadcast, message history

## Tech Stack

| Category | Technology |
|----------|-----------|
| Language | Python 3.10+ |
| Data validation | pydantic |
| CLI | click |
| Testing | pytest, pytest-cov, ruff |

## Project Structure

```
agent-sim/
├── src/agent_sim/
│   ├── __init__.py
│   ├── cli.py                    # CLI entry point
│   ├── agent/
│   │   ├── __init__.py
│   │   └── base.py               # DONE: Agent ABC + Config/State
│   ├── communication/
│   │   ├── __init__.py
│   │   └── bus.py                # DONE: Message + MessageBus
│   ├── environment/              # TODO: Environment sandbox
│   ├── scenario/                 # TODO: Scenario runner
│   └── metrics/                  # TODO: Metrics collection
├── tests/
│   ├── conftest.py               # Shared fixtures (EchoAgent, CountingAgent)
│   ├── test_agent.py             # 13 tests
│   └── test_communication.py     # 9 tests
└── pyproject.toml
```

## Installation

```bash
git clone https://github.com/Jane-o-O-o-O/agent-sim.git
cd agent-sim
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Usage Example

```python
from agent_sim.agent import Agent, AgentConfig
from agent_sim.communication import Message, MessageBus

class MyAgent(Agent):
    def act(self):
        # process inbox, decide action
        for msg in self._inbox:
            print(f"Received: {msg.content}")
        self._inbox.clear()
        return {"action": "respond"}

# Create agents
a1 = MyAgent(AgentConfig(name="agent-1"))
a2 = MyAgent(AgentConfig(name="agent-2"))

# Register on communication bus
bus = MessageBus()
bus.register(a1)
bus.register(a2)

# Communicate
bus.send(Message(sender=a1.id, receiver=a2.id, content="hello"))

# Simulation loop
for step in range(10):
    a1.step({"env_step": step})
    a2.step({"env_step": step})
```

## Roadmap

- [x] **v0.1.0** - Agent base class + MessageBus (DONE)
- [ ] **v0.2.0** - Environment sandbox (Sandbox, EnvironmentState)
- [ ] **v0.3.0** - Scenario definition and runner (Scenario, ScenarioRunner)
- [ ] **v0.4.0** - Evaluation metrics (MetricsCollector, Reporter)
- [ ] **v0.5.0** - CLI improvements (agent-sim run, list, report)
- [ ] **v1.0.0** - Stable API, complete documentation

## License

MIT License (c) 2026 Jane-o-O-o-O
