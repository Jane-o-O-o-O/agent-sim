"""CLI entry point for Agent Sim."""
import click


@click.group()
@click.version_option(package_name="agent-sim")
def main():
    """Agent Sim - Multi-agent simulation framework."""
    pass


@main.command()
@click.option("--config", required=True, help="Scenario config file path")
@click.option("--steps", default=10, help="Number of simulation steps")
def run(config, steps):
    """Run a simulation scenario."""
    click.echo(f"Running scenario from {config} for {steps} steps")


@main.command("list-agents")
def list_agents():
    """List registered agents."""
    click.echo("No agents registered yet.")


@main.command()
@click.option("--run-id", required=True, help="Simulation run ID")
def report(run_id):
    """Show simulation report."""
    click.echo(f"Report for run: {run_id}")


if __name__ == "__main__":
    main()
