"""SkillRadar — Python data-engineering rebuild.

A read-only job-market intelligence pipeline: ingests real tech postings from public
ATS feeds (Greenhouse/Lever/Ashby), runs a Medallion (Bronze/Silver/Gold) pipeline on
DuckDB + Parquet, extracts required skills, and serves a Streamlit dashboard.
"""

__version__ = "0.1.0"
