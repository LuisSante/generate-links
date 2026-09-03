# Environment setup (uv + Scrapy)

## uv environment

```bash
# install uv (once)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

```bash
# create the project (pyproject.toml only)
uv init --bare
```

```bash
# add dependencies (creates .venv and uv.lock)
uv add scrapy
```

```bash
# reproduce the environment on another machine (after clone)
uv sync
```

No need to activate the venv — `uv run <cmd>` resolves it automatically.

## Scrapy

```bash
# check install
uv run scrapy version
```

```bash
# create the Scrapy project
uv run scrapy startproject links_scraper
```

```bash
# generate a spider
cd links_scraper
uv run scrapy genspider example example.com
```

```bash
# run a spider
uv run scrapy crawl example -o output.json
```
