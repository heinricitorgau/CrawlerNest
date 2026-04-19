# Lobster-01 Node Operations Guide

This directory is the canonical runtime environment for **Lobster-01** (Low-spec crawler node).

## Design Philosophy
- **Stability > Speed**: Single worker, high delay (10s+) to avoid WAF blocks.
- **Resource Guard**: Low CPU/Memory footprint to ensure system stability.
- **Resilience**: Checkpoint-based execution for long-running jobs.

## Quick Start

### 1. Execute the Pipeline
Run the optimized production-safe script:
```bash
./run_lobster.sh
```

### 2. Configuration
The parameters are pre-tuned for Lobster-01 in `node_config.json`. 
- `workers: 1`
- `request_delay: 10.0`
- `write_batch_size: 100`

### 3. Logs
Logs are stored in `logs/` inside this directory.

## Maintenance
- Ensure the PostgreSQL service is reachable from this node.
- Check disk space periodically if `raw_json` export is enabled.
