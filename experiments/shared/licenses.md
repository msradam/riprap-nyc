# Experiment model license ledger

Every model loaded by an experiment must be Apache-2.0, MIT, or BSD.
Verified against the actual `LICENSE` file in the upstream repo, not
just the HF metadata field. Update this file the moment a new model
enters an experiment.

| Model | HF ID | License | LICENSE source | Verified |
|-------|-------|---------|----------------|----------|
| Prithvi-EO 2.0 (Sen1Floods11 fine-tune) | ibm-nasa-geospatial/Prithvi-EO-2.0-300M-TL-Sen1Floods11 | Apache-2.0 | Model card frontmatter `license: apache-2.0` | 2026-05-02 |
| GLiNER medium v2.1 | urchade/gliner_medium-v2.1 | Apache-2.0 | HF cardData.license = "apache-2.0"; **NOT to be confused with gliner_base which is CC-BY-NC-4.0** | 2026-05-02 |
| Granite Embedding Reranker R2 (English) | ibm-granite/granite-embedding-reranker-english-r2 | Apache-2.0 | HF cardData.license = "apache-2.0" | 2026-05-02 |
| Granite Guardian 3.2 3B-A800M | ibm-granite/granite-guardian-3.2-3b-a800m | Apache-2.0 | HF cardData.license = "apache-2.0"; transformers + safetensors; intended for BYOC adversarial filtering | 2026-05-03 |
| TerraMind 1.0 base | ibm-esa-geospatial/TerraMind-1.0-base | Apache-2.0 | README frontmatter `license: apache-2.0`; HF cardData confirms. **No separate `LICENSE` file in repo** (IBM repo norm — cardData is canonical for IBM/ESA models). arXiv:2504.11171 cross-references IBM's standard Apache-2.0 release posture. | 2026-05-02 |
| TerraMind 1.0 base — encoder backbone (`terramind_v1_base`) | (same repo, encoder variant) | Apache-2.0 | Same weights as above; the BACKBONE_REGISTRY variant exposes the encoder for fine-tuning. Verified via `experiments/05a_terramind_finetune_micro/micro.py` on AMD MI300X. | 2026-05-03 |

## Auditing checklist (per model)

- [ ] HF model page metadata says one of: `apache-2.0`, `mit`, `bsd-*`
- [ ] Repo's `LICENSE` file confirms the same license verbatim
- [ ] If the model wraps a base model with a different license, the
      base's LICENSE is also tracked here and ALL of base+wrapper are
      acceptable
- [ ] Date verified is the date the LICENSE file was last fetched
