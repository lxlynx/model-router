<div align="center">

# model-router

**Rule-based model routing for LLM requests — no embeddings, no learned weights, a rules engine you can debug at 3am.**

[![python](https://img.shields.io/badge/python-3.8%2B-blue?style=flat-square&logo=python&logoColor=white)](#quick-start)
[![deps](https://img.shields.io/badge/dependencies-standard%20library-lightgrey?style=flat-square)](#quick-start)
[![license](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)

</div>

## About

Every team that runs more than one model ends up with routing logic
spread across if-statements and environment variables. This replaces that with
an ordered rule list that is first-match-wins and, critically, **explains its
decision**: given a request you can print the winning rule and why every
earlier rule did not apply.

No embeddings and no learned weights means the behaviour is reproducible
offline and diffable in review, which is worth more than the few percent of
accuracy a scorer might add.

## Quick start

```bash
git clone https://github.com/lxlynx/model-router
cd model-router
python3 -m unittest -v
```

## Configuration

| Key | Description |
| --- | --- |
| `task type` | classification, extraction, summarisation, code |
| `cost ceiling` | maximum price per 1k tokens the rule may pick |
| `context length` | prompt size band, which rules out small-context models |
| `rules file` | ordered, first-match-wins; print the winner with its reason |
## Roadmap

- [ ] Per-provider price table refresh script
- [ ] Dry-run mode that replays a request log
- [ ] Metrics export of rule hit counts

## Contributing

Issues and pull requests are welcome. Please keep changes small and focused,
and add a test for any behaviour change — every repository here ships with a
runnable test suite and no third-party dependencies, so CI is just
`python3 -m unittest` / `bash test_*.sh`.

## License

[MIT](LICENSE)
