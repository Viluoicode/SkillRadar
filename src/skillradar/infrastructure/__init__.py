"""Infrastructure layer — concrete adapters that implement the application ports.

This is the only layer allowed to import I/O technologies (``duckdb``, ``httpx``,
``pandas``, the filesystem). Everything here is swappable behind a port."""
