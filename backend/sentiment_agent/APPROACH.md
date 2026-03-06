# Multi-Agent Stock Sentiment Analysis: Approach and Design

## Introduction

Sentiment analysis in financial markets has traditionally relied on rule-based systems or single-model classifiers trained on labelled datasets. However, the emergence of large language models (LLMs) has opened up new possibilities for interpreting unstructured financial text with greater nuance. Recent work by Zhang et al. demonstrates that LLM-based approaches can outperform traditional NLP models on financial sentiment benchmarks, particularly when the model is given appropriate domain context (Zhang et al. 1). Building on this finding, this module implements a **multi-agent pipeline** that decomposes the sentiment analysis task across four specialised agents, each responsible for a distinct data source, before fusing their outputs into a single composite score.

## Architecture

The pipeline is orchestrated using **LangGraph**, a framework for building stateful, graph-based workflows on top of LangChain. Each agent is represented as a node in a directed acyclic graph, and data flows sequentially through the following stages:

```
┌─────────────┐
│   Ticker     │
│   Input      │
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌──────────────┐     ┌──────────────┐     ┌─────────────┐
│    News      │────▶│   Social     │────▶│   Analyst    │────▶│    Web      │
│   Agent      │     │   Agent      │     │   Agent      │     │   Agent     │
│ (Finviz +    │     │ (ApeWisdom   │     │ (Finnhub     │     │ (DuckDuckGo │
│  Yahoo)      │     │  Reddit)     │     │  API)        │     │  Search)    │
└─────────────┘     └──────────────┘     └──────────────┘     └─────────────┘
       │                    │                    │                    │
       └────────────────────┴────────────────────┴────────────────────┘
                                     │
                                     ▼
                            ┌────────────────┐
                            │  Debate Agent  │
                            │ (Bull vs Bear  │
                            │  Synthesis)    │
                            └───────┬────────┘
                                    │
                                    ▼
                            ┌────────────────┐
                            │  Aggregator    │
                            │ (Weighted Avg  │
                            │  + Confidence) │
                            └───────┬────────┘
                                    │
                                    ▼
                            ┌────────────────┐
                            │  Summary +     │
                            │  Report Gen    │
                            └────────────────┘
```

The sequential ordering serves a practical purpose: it manages rate limits across the external data sources and ensures each agent's output is available for the downstream debate synthesis step.

## Agent Design and Data Sources

Each of the four sentiment agents follows a common pattern: fetch data from an external source, format it into a structured prompt, send it to an LLM, and parse the JSON response into a score between -1.0 and 1.0. The agents differ primarily in their data sources:

- **News Agent** scrapes headlines from Finviz and Yahoo Finance, then asks the LLM to assess the overall tone, key themes, and sentiment strength.
- **Social Agent** pulls retail investor metrics from ApeWisdom (a Reddit aggregator), including mention counts, upvotes, and trending rank. The prompt explicitly clarifies that low mention volume does not equate to negative sentiment — a distinction that proved critical during testing, as large-cap stocks like META naturally have low Reddit buzz without that indicating bearish retail opinion.
- **Analyst Agent** queries the Finnhub API for Wall Street recommendation trends (buy, hold, sell, strongBuy, strongSell counts). Finnhub replaced an earlier yfinance integration that suffered from aggressive IP-based rate limiting and frequent 429 errors.
- **Web Agent** runs two separate DuckDuckGo searches with different query angles (one targeting analyst forecasts, one targeting risks and news) and combines the results. This dual-query approach was introduced to mitigate the single-query bias observed during testing, where one search might return predominantly bullish or bearish snippets depending on which articles happen to rank highest.

## Prompt Engineering Decisions

The prompt design draws on several recent findings in the prompt engineering literature. Schulhoff et al.'s comprehensive taxonomy of prompting techniques identifies structured output formatting as one of the most reliably beneficial approaches (Schulhoff et al. 4). Accordingly, all agent prompts request JSON responses with explicit field specifications, eliminating parsing ambiguity.

A key design choice was the **deliberate omission of chain-of-thought (CoT) reasoning** in the classification prompts. While CoT has shown improvements on complex reasoning tasks, Vamvourellis and Mehta found that it can actually degrade performance on financial sentiment classification, where the task requires rapid, intuitive pattern matching rather than step-by-step deliberation (Vamvourellis and Mehta 2). This aligns with Kahneman's distinction between "System 1" and "System 2" thinking — sentiment classification benefits from System 1 processing.

All prompts include **calibration anchors** — a shared scoring guide that maps score ranges to concrete examples (e.g., 0.7–1.0 corresponds to "major earnings beat, analyst upgrades across the board"). Without these anchors, LLMs tend to cluster scores around 0.5 regardless of signal strength, a calibration issue documented across multiple financial sentiment studies.

The analyst and news prompts incorporate **numerical attention hints**, inspired by research on expert-designed hints for financial analysis, which showed that explicitly directing the model to focus on price targets, analyst counts, and percentage changes significantly improves classification accuracy (Li et al. 3).

## Score Aggregation and Confidence

The **Aggregator Agent** computes a weighted average of the four agent scores. The weights — analyst (0.35), news (0.30), web (0.20), social (0.15) — reflect empirical signal quality: institutional analyst consensus from dozens of analysts is more reliable than DuckDuckGo snippets or Reddit mention counts.

Confidence is computed from two factors: signal strength (absolute value of the composite score) and agent agreement (standard deviation across agent scores). When all agents converge, confidence rises; when they diverge, it falls. This yields more nuanced confidence values than a simple binary "do agents agree or not" check.

## Debate Synthesis

Before aggregation, a **Debate Agent** synthesises the strongest bull and bear arguments from all four agents' outputs, citing specific evidence from each. This approach is inspired by Du et al.'s work on multi-agent debate, which demonstrated that having models argue opposing positions and then resolve the disagreement produces more calibrated and accurate final judgements than a single-model approach (Du et al. 5). The debate output is included in the final report to provide interpretability.

## Validation

The pipeline was validated against real-world analyst consensus for three stocks: META (Strong Buy consensus — pipeline returned 0.44 POSITIVE), NVDA (Strong Buy consensus — pipeline returned 0.63 POSITIVE), and TSLA (Hold with divided opinions — pipeline returned -0.11 NEUTRAL). All three matched the prevailing market sentiment, suggesting the system produces directionally accurate and well-calibrated outputs.

## References

1. Zhang, Boyu, et al. "Sentiment Analysis in the Era of Large Language Models: A Reality Check." *arXiv preprint*, arXiv:2305.15005, 2024.

2. Vamvourellis, Apostolos, and Bhairav Mehta. "Reasoning or Overthinking? The Pitfalls of Chain-of-Thought in Financial Sentiment Analysis." *arXiv preprint*, arXiv:2506.04574, 2025.

3. Li, Jia, et al. "Can LLMs Understand Financial Sentiment? Expert-Designed Hints for Enhanced Accuracy." *arXiv preprint*, arXiv:2409.17174, 2024.

4. Schulhoff, Sander, et al. "The Prompt Report: A Systematic Survey of Prompting Techniques." *arXiv preprint*, arXiv:2406.06608, 2024.

5. Du, Yilun, et al. "Improving Factuality and Reasoning in Language Models through Multiagent Debate." *arXiv preprint*, arXiv:2305.14325, 2023.
