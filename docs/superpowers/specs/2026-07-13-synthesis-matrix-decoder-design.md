# Synthesis Matrix Decoder Design

Date: 2026-07-13

## Purpose

Add one visual slide immediately after the cross-team synthesis matrix so three compressed comparison labels are understandable without prior recommender-systems terminology:

1. rich reranker features;
2. full candidate union or late fusion; and
3. factual grounding.

The slide must answer four questions for each term: what it means, what the submitted system had, what it lacked, and why the distinction matters.

## Presentation

The existing synthesis matrix remains unchanged and compact. A new slide titled **“Decode three important rows”** follows it in both curated and audit navigation.

The slide uses three large, color-coded mechanism cards rather than a prose block. Each card contains:

- a short plain-language definition;
- a small left-to-right mechanism diagram;
- a green **We had** group;
- an amber **We lacked** group; and
- a one-sentence **Why it matters** conclusion.

The cards are visible without hover. Detailed evidence and source markers may remain behind disclosures elsewhere in the report.

## Card 1: Reranker Evidence Breadth

Plain-language definition: reranker features are the signals LightGBM can inspect for candidates that already reached it. “Rich” means diverse, decision-relevant evidence, not merely a high feature count.

The submitted system had 142 documented features, including:

- per-branch rank, score, presence, margin, ratio, and percentile evidence;
- dense and multimodal similarity;
- CF/BPR anchor and user centroid similarity;
- state, intent, rejection, history, routing, and cross-source agreement;
- catalog metadata, artist, album, tag, era, duration, popularity, culture, and age fields.

The concrete evidence not documented in the deployed feature path was:

- direct track co-occurrence sum, maximum, probability, or dedicated lane membership;
- sequential or Markov transition probability;
- candidate-producing learned-retriever presence, rank, or score from the trained two-tower;
- systematic grounded generated-description similarity;
- stronger explicit behavior-derived frequency or transition priors.

The slide must not say that all 142 features were weak or that feature count caused the Blind-B result.

## Card 2: Full Candidate Union and Late Fusion

Plain-language definition: candidate construction decides which tracks a reranker is allowed to consider. A full union retains the deduplicated candidates produced by all sources. Late fusion keeps source evidence separate until a later scorer combines it, rather than collapsing or pruning it too early.

The submitted system:

- collected up to 500 hits from each traced retrieval branch;
- applied branch-specific filtering and formed their union; and
- let LightGBM produce the submitted final ordering of candidates in that union.

The limitation is not that RRF was used with LightGBM; it was not. The limitation is that tracks never emitted by a deployed branch, or removed before the union reached LightGBM, were unrecoverable. The trained two-tower contributed a feature but not a candidate-producing lane.

The comparison card may name niwatori’s full ordered union and team2_s2’s later/routed combination as documented examples. It must preserve evidence boundaries and avoid claiming that either mechanism caused the score difference.

## Card 3: Factual Grounding

Plain-language definition: factual grounding constrains response claims to information that can be traced to the selected track, conversation state, catalog, or another verified record.

The ideal visual sequence is:

**selected track → verified fact bundle → allowed claims → checker or repair step → final response**

The submitted path had the selected track, latest state, and track/catalog metadata. It did not document:

- an independent structured fact checker;
- citation or theme validation;
- a separate repair pass for unsupported claims; or
- selection among multiple grounded drafts.

This is why the synthesis matrix says **Partial**, not **Not documented**: the response had grounded inputs, but not the stronger verification-and-repair controls documented by some leaders.

## Responsive and Accessible Behavior

- Desktop and tablet show three cards in a balanced grid when space permits.
- Narrow screens stack the cards vertically.
- Text remains readable without horizontal scrolling.
- Color is supplemented by headings and labels.
- Definitions and contrasts are real text, not background images.
- The slide introduces no hover-only information.

## Testing

Tests must first fail for the absent slide and then verify:

- the new slide follows the synthesis matrix;
- all three terms and plain-language definitions are visible;
- the missing reranker evidence is named explicitly;
- the candidate diagram says up to 500 hits from each traced branch and does not claim RRF fed LightGBM;
- factual grounding visibly includes verified facts and checking or repair;
- the slide fits the supported desktop, tablet, and mobile viewports without unintended horizontal overflow;
- curated navigation includes the decoder after the synthesis matrix.

## Evidence Boundary

The slide explains documented mechanisms and evidence gaps. It does not claim causal attribution for the hidden Blind-B outcome. “Missing” means not documented in the reviewed deployed path unless the report explicitly states otherwise.
