# Contributing to Data Scraper Engine

First off, thank you for considering contributing! 🎉

## 🐛 Bug Reports

- Use [GitHub Issues](https://github.com/ccjiao/data-scraper-engine/issues)
- Include: Python version, OS, full error traceback, URL that caused the issue
- Search existing issues before creating a new one

## 💡 Feature Requests

- Open an Issue with the `enhancement` label
- Describe the use case and the data source you want to scrape
- If you plan to implement it yourself, mention that in the issue

## 🔧 Pull Requests

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-adapter`)
3. Make your changes
4. Add tests if applicable
5. Ensure existing tests pass
6. Commit with a clear message
7. Push to your fork and submit a Pull Request

### Code Style

- Python 3.10+ (use type hints)
- Follow PEP 8
- Docstrings in English (comments can be Chinese)
- Max line length: 120

### Adding a New Data Source

The best way to contribute is adding support for new data sources:

1. **Create a YAML config** in `configs/` — see existing configs for the format
2. **Add URL routing rules** in `engine/router.py` — add a new rule to the `RULES` list
3. **Create an adapter** (optional) — only if the data source uses a new protocol
4. **Create a parser** (optional) — only if the data needs special parsing
5. **Test it** — verify with real URLs
6. **Document it** — add the URL pattern to README.md

## 📜 License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
