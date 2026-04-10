# Mini Agent for CrawlerNest

This project is a minimal AI agent system intended to become a sub-agent inside the broader CrawlerNest platform.

It supports:

- a generate -> evaluate -> refine loop
- a CLI dev-agent mode
- a small FastAPI chat API

## Run the CLI

From the `mini_agent/` directory:

```bash
python cli/run_agent.py --task "fix extractor"
```

Example tasks:

```bash
python cli/run_agent.py --task "generate parser"
python cli/run_agent.py --task "summarize current task"
```

## Run the Web Server

Install dependencies:

```bash
pip install -r requirements.txt
```

Start the FastAPI server from the `mini_agent/` directory:

```bash
uvicorn web.app:app --reload
```

Then send a request:

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"fix extractor"}'
```
