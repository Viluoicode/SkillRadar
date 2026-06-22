"""Use-case services: thin orchestrators that load via a repository, apply a domain rule,
and persist the result. They hold no SQL and no I/O — only the wiring of ports to rules."""
