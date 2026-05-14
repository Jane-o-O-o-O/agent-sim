# Changelog

All notable changes to Agent Sim will be documented in this file.

Format: [Keep a Changelog](https://keepachangelog.com/)

## [1.0.0] - 2026-05-15

### Added
- **Custom Exception Hierarchy** — 18 specialized exception types (`AgentSimError`, `ConfigError`, `AgentTypeError`, `TopologyError`, `LLMError`, etc.) with backward-compatible inheritance from standard Python exceptions
- **Configuration Validation** — `validate_scenario()` returns ALL errors at once, not just the first
- **JSON Schema Export** — `config_schema()`, `config_schema_json()`, `config_schema_yaml()` for IDE integration
- **CLI: `agent-sim doctor`** — Check Python version, dependencies, registered Agent types
- **CLI: `agent-sim schema`** — Export YAML config schema in JSON/YAML format
- **CLI: `agent-sim completion`** — Shell completion setup for Bash/Zsh/Fish
- **Enhanced `agent-sim validate`** — Multi-error reporting with detailed messages
- **PEP 561 `py.typed`** marker for static type checker support

### Changed
- All internal exceptions now use specialized types from `agent_sim.exceptions`
- Exception hierarchy designed for backward compatibility (custom exceptions inherit from standard Python exceptions)

## [0.9.0] - 2026-05-14

### Added
- **SimulationMonitor** — Real-time step snapshots with configurable alert thresholds
- **TopologyScheduler** — Dynamic topology rule engine for step-based switching
- **CommunicationProtocol** — Structured protocols: RoundRobin, BroadcastCollect, Consensus, FreeForm
- **ScenarioTemplates** — 6 built-in templates (ping_pong, debate, brainstorm, code_review, task_delegation, multi_round_discussion)
- **ConversationGraph** — Message flow visualization (Mermaid sequence diagrams, ASCII matrix, flow summary)
- CLI: `agent-sim init` — Create YAML from templates
- CLI: `agent-sim graph` — Generate communication graphs

## [0.8.0] - 2026-05-13

### Added
- **AsyncEventBus** — Async pub/sub event system with subscribe/publish/unsubscribe
- **DynamicTopology** — Step-based topology snapshots with history
- **BenchmarkRunner** — Performance benchmarks with scale tests and concurrency tests
- **AgentHealthMonitor** — Heartbeat detection, error tracking, auto-recovery
- **MetricAggregator** — Percentiles (P50/P90/P99/P99.9), histograms, trend analysis
- **PluginRegistry** — Auto-discovery of agent/evaluator/middleware plugins
- CLI: `agent-sim benchmark` — Run performance benchmarks
- CLI: `agent-sim plugins` — View registered plugins

## [0.7.0] - 2026-05-12

### Added
- **ReplayEngine** — Event playback with step-by-step iteration, filtering, timeline
- **BatchRunner** — Batch simulation runs with statistical analysis (mean, std, min, max)
- **HTMLReport** — Rich HTML reports with embedded charts
- **Scenario Inheritance** — `extends` field for config inheritance
- CLI: `agent-sim replay` — Replay event logs
- CLI: `agent-sim batch` — Batch run simulations

## [0.6.0] - 2026-05-11

### Added
- **Agent Registry** — Register/unregister custom agent types
- **EventRecorder** — Timestamped event logging with JSON export
- **Simulation Timeout** — Configurable timeout with graceful shutdown
- CLI: `agent-sim compare` — Side-by-side scenario comparison
- CLI: `agent-sim report` — Terminal visualization report
- Built-in scenario examples (ping-pong, multi-agent echo)

## [0.5.0] - 2026-05-10

### Added
- **MemoryAgent** — LLM agent with auto-injected conversation buffer and fact memory
- **Middleware Pipeline** — Logging, Filter, Transform, RateLimit, Deduplication middleware
- **ResponseTracker** — Request-response correlation with timeout
- **Checkpointing** — Save/restore simulation state
- **RetryManager** — Configurable retry with exponential backoff
- **Concurrent Execution** — Parallel agent stepping
- **CSV Export** — Message export in CSV format

## [0.4.0] - 2026-05-09

### Added
- **Memory System** — ConversationBuffer, SlidingWindowBuffer, KeyFactMemory
- **NetworkTopology** — mesh/star/chain/tree/ring/custom topologies
- **ASCII Visualization** — Bar charts, line charts, sparklines, metrics tables
- **DebateAgent** — Structured debate with proponent/opponent stances
- **CollaborateAgent** — Coordinator/worker/reviewer collaboration patterns

## [0.3.0] - 2026-05-08

### Added
- **OpenAIBackend** — Async OpenAI-compatible API with httpx
- **OllamaBackend** — Local model server integration
- **Evaluation System** — EvalSuite with 6 evaluators (Completion, Participation, Flow, Latency, Volume, Network)
- **Lifecycle Hooks** — 7 hook points for simulation lifecycle events
- **Export** — JSON and Markdown message export

## [0.2.0] - 2026-05-07

### Added
- **YAML Configuration** — Declarative scenario definitions
- **LLMAgent** — LLM-driven agent with pluggable backends
- **ToolAgent** — Tool registration and execution
- **Logging** — Structured logging with configurable levels
- CLI: `agent-sim run`, `agent-sim validate`, `agent-sim info`

## [0.1.0] - 2026-05-06

### Added
- **Agent ABC** — Base agent class with `step()` pattern
- **MessageBus** — Agent-to-agent message routing (direct/broadcast)
- **Sandbox** — Simulation environment with state management
- **ScenarioRunner** — Step-based simulation loop
- Initial project structure with Pydantic models
