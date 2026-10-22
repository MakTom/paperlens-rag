# Small fixed corpus
Five real paper IDs/titles with original short summaries prepared for this tutorial.
The abstract field contains an authored summary, NOT the paper's verbatim abstract.
Every row records text_kind=authored_summary and the source landing-page URL.
Sources were checked on 22 October 2026. No PDF, scraped full text or model-generated
answer is required to run the seed command.

This is fixture version 1. Commit it so baseline retrieval uses fixed inputs.
Day 8 will introduce live ingestion; explicitly replace summaries with fetched
abstracts in that later workflow. The Day 3 seed deliberately does not update
existing rows, even if you edit the fixture.

Sources:
- https://arxiv.org/abs/2005.11401
- https://arxiv.org/abs/1706.03762
- https://arxiv.org/abs/1810.04805
- https://arxiv.org/abs/2004.04906
- https://arxiv.org/abs/1910.13461
