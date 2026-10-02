"""Pure, model-free comparison logic shared by S08/S10/S11.

Everything in this package is deterministic text analysis — no embeddings, no
NER, no I/O — so it can be unit-tested with Bengali fixtures. Stages feed it
model outputs (entity mentions, similarity numbers) and read back explicit
states and evidence-backed discrepancies.
"""
