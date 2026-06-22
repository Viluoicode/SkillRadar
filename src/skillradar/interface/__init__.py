"""Interface layer — drivers and composition roots (CLI, Prefect flow, dashboard wiring).

This is where concrete infrastructure adapters are constructed and injected into the
application use-cases. It is the outermost layer and may depend on everything below it."""
