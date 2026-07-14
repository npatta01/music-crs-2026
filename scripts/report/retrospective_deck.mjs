#!/usr/bin/env node
import { readFile, rename, writeFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";

const slide = (slug, title, archetype, blocks, options = {}) => ({ slug, title, archetype, blocks, ...options });

export const PAGE_ARCHETYPES = new Set(["cover", "story", "visual", "matrix", "audit"]);

export const CONFIDENCE_LEVELS = new Set(["verified", "likely", "unknown"]);

export const DIAGNOSIS_SLIDES = [
  slide("score-location", "Where the score gap appeared", "visual", [], {
    diagnosisKind: "score",
    takeaway: {
      text: "Ranking and judge terms explain most of the arithmetic gap; the chart does not prove which mechanism caused it.",
      confidence: "verified",
    },
  }),
  slide("information-loss", "Where information was lost", "visual", [], {
    diagnosisKind: "bottleneck",
    stages: ["Conversation", "Extracted state", "Retriever actions", "Candidate sources", "Candidate union", "LightGBM", "Top-1 track", "Grounded context", "One draft", "Final response"],
    losses: [
      { after: "Extracted state", label: "Some facts remained soft or lacked a dedicated source action", confidence: "verified" },
      { after: "Candidate sources", label: "No direct co-occurrence or transition lane", confidence: "verified" },
      { after: "Candidate union", label: "Absent tracks were irrecoverable downstream", confidence: "verified" },
      { after: "One draft", label: "No independent selection, checking, or repair", confidence: "verified" },
    ],
  }),
  slide("constraint-wiring", "Extracted constraints versus operationalized constraints", "visual", [], {
    diagnosisKind: "wiring",
    connections: [
      { from: "Explicit rejections", to: "Hard track exclusion, tag demotion, and artist veto", confidence: "verified" },
      { from: "Era preference", to: "Soft preference and era lookup", confidence: "verified" },
      { from: "Played-track history", to: "Anchors and reranker features, without a direct track co-occurrence source", confidence: "verified" },
      { from: "Other soft state facts", to: "No dedicated source action documented for every field", confidence: "verified" },
    ],
    takeaway: {
      text: "Rich extraction, uneven execution: not every fact became a filter, source-specific query, or dedicated candidate signal.",
      confidence: "verified",
    },
  }),
  slide("features-seen", "What the 142-feature reranker saw", "visual", [], {
    diagnosisKind: "feature-map",
    featureFamilies: ["Retriever evidence", "Semantic and multimodal", "Behavioral and lookup", "Catalog", "Conversation and state", "Agreement and interactions"],
    takeaway: {
      text: "The ranker was substantial; column count alone does not establish liveness, importance, robustness, or held-out benefit.",
      confidence: "verified",
    },
  }),
  slide("evidence-missed", "Evidence the ranker could not see or recover", "visual", [], {
    diagnosisKind: "boundaries",
    boundaries: ["Missing upstream source", "Consequent missing feature", "Not missing"],
    takeaway: {
      text: "Adding LightGBM columns cannot recreate a track or source signal that never entered the pipeline.",
      confidence: "verified",
    },
  }),
  slide("confidence", "Response weakness and confidence-ranked diagnosis", "visual", [], {
    diagnosisKind: "confidence",
    confidence: {
      verified: ["Ranking and judge dominate the score gap", "Constraint execution was uneven", "Behavioral evidence was partial", "b1_cos was a reranker feature only", "Blind-B used one response call with echo_retries=0"],
      likely: ["Evidence diversity mattered more than feature count", "LLM knowledge was not consistently grounded and reused", "Distribution shift or objective mismatch contributed", "Response quality control was too thin"],
      unknown: ["Blind-B candidate recall", "Present-but-misranked frequency", "Per-session failure archetypes", "Causal effect of any one mechanism"],
    },
  }),
];

export const CURATED_PATH = [
  "outcome/executive-answer", "outcome/gap-chart",
  ...DIAGNOSIS_SLIDES.map(({ slug }) => `diagnosis/${slug}`),
  "ours/inference-rail", "retrieval/evidence-heatmap", "response/control-heatmap",
  "leaders/volart-retrieval", "synthesis/decoder", "synthesis/lessons",
];

const provenanceLayers = ["Official challenge data", "External structured data", "Generated artifacts", "Latent LLM knowledge", "Verification boundary"];
const evidenceColumns = ["Lexical", "Dense", "Collaborative", "Co-occurrence", "Transition", "Lookup", "Generated description", "Metadata", "Conversation/state", "Agreement/routing", "Priors"];
const responseColumns = ["Grounding", "Drafts", "Selection", "Verification", "Repair", "Lexical control"];
const cell = (status, label, short = label) => ({ status, label, short });

export const LEADER_SYSTEM_CARDS = {
  volart: {
    result: "0.5866 composite · 0.3965 nDCG@20 · 4.90/5 judge",
    query: "GPT-4o-mini produced one cached retrieval rewrite plus positive entity and era JSON.",
    knowledge: "Official records, train co-occurrence and frequency/MOVES priors, plus generated track descriptions.",
    retrieval: "Five lanes fed a top-500 LambdaMART boundary with direct co-occurrence features.",
    response: "Three drafts, independent critique, selective rewrite, hardening, and lexical control.",
    limit: "Structured musical-fact verification was not documented.",
  },
  niwatori: {
    result: "0.5859 composite · 0.4934 nDCG@20 · 4.45/5 judge",
    query: "Source-specific safe text, full played history, and last-track transition keys; no LLM retrieval rewrite documented.",
    knowledge: "Official records plus mapped TalkPlayData-1 co-occurrence and transition statistics.",
    retrieval: "Fourteen-source union, direct co-occurrence, Markov transition, and 176 documented features with OOF artifacts.",
    response: "Ten seeded drafts selected for lexical diversity.",
    limit: "The selector was not a factual critic; response fact checking was not documented.",
  },
  swyoo: {
    result: "0.5784 composite · 0.3829 nDCG@20 · 4.85/5 judge",
    query: "Separate BM25, QEmb, and two-tower representations with an optional cached session summary.",
    knowledge: "LRCLIB, Genius, and MusicBrainz enriched lyrics, identifiers, tags, labels, countries, and dates.",
    retrieval: "Three independently rendered pools with group-aware OOF routing for learned sources.",
    response: "PAS generation with theme/citation validation and repair.",
    limit: "One PAS prediction was used; no best-of-N independent critic was documented.",
  },
  team2_s2: {
    result: "0.5759 composite · 0.4452 nDCG@20 · 4.65/5 judge",
    query: "Conversation BM25, live text, recent item vectors, ALS history, and cached structured lists.",
    knowledge: "Official catalog, conversations, users, labels, and embeddings; no external music dataset documented.",
    retrieval: "Live and structured sources fed routed rankers with covariate-shift weighting and 37 documented features.",
    response: "Verified catalog facts grounded a first draft followed by Gemini Pro refinement.",
    limit: "No independent structured fact or recommendation-ID integrity check was documented.",
  },
};

export const CHAPTERS = [
  {
    slug: "outcome",
    title: "Outcome & score",
    question: "What happened, and which metric terms made the gap?",
    slides: [
      slide("cover", "Outcome & score", "cover", []),
      slide("executive-answer", "Executive answer", "story", ["title", "executive_summary", "headline_metrics", "section_directory"]),
      slide("leaderboard-chart", "How the result was scored", "visual", ["how_scoring_works", "final_result_heading", "leaderboard_chart"]),
      slide("leaderboard-table", "Exact leaderboard", "matrix", ["leaderboard_table"]),
      slide("gap-chart", "Gap decomposition", "visual", ["gap_contribution_chart"]),
      slide("gap-interpretation", "What the score gap does—and does not—show", "story", ["gap_interpretation"], { scoreFindings: true }),
    ],
  },
  {
    slug: "diagnosis",
    title: "Diagnosis",
    question: "Where did information and control weaken, and how confident is that diagnosis?",
    slides: DIAGNOSIS_SLIDES,
  },
  {
    slug: "ours",
    title: "Our submission",
    question: "What did we build, what worked, and where did confidence fail?",
    slides: [
      slide("cover", "Our submission", "cover", ["own_system_heading"]),
      slide("offline-rail", "Offline evidence rail", "visual", ["own_system_diagram"]),
      slide("inference-rail", "Inference rail", "visual", [], { lanes: [
        { label: "Deployed Blind-B path", steps: ["DeepSeek state extraction", "BM25, multimodal ANN, and lookup branches", "Up to 500 hits from each traced branch → candidate union", "LightGBM LambdaMART reorders the union", "Top-1 selected track", "Single-pass response"] },
      ] }),
      slide("walkthrough", "Complete walkthrough and ranking handoff", "audit", ["own_system_walkthrough"]),
      slide("what-worked", "What worked", "story", ["what_worked"]),
      slide("evaluation-mistake", "Evaluation mistake and confidence boundary", "story", ["evaluation_mistake"]),
      slide("contributors", "Ranking and response contributors", "story", ["ranking_contributors", "response_contributors"]),
    ],
  },
  {
    slug: "query",
    title: "Conversation → query",
    question: "How did each system turn dialogue into retriever inputs?",
    slides: [
      slide("cover", "Conversation → query", "cover", []),
      slide("lifecycle", "Dialogue becomes several search signals", "visual", ["lifecycle_heading", "lifecycle_map", "lifecycle_takeaway", "query_heading", "query_explainer"], {
        visualKind: "mechanism",
        takeaway: "The important choice is not one perfect query. It is which conversation evidence becomes useful input for each retrieval lane.",
        stages: [
          { label: "Conversation window", detail: "Recent turns, longer history, and played tracks" },
          { label: "Interpretation", detail: "State, rewrite, entities, summary, or learned encoding" },
          { label: "Query variants", detail: "Lexical, dense, history, transition, and constraint signals" },
          { label: "Retriever inputs", detail: "Each source receives the representation suited to its evidence" },
        ],
      }),
      slide("query-matrix", "Same stages, different query evidence", "matrix", ["query_matrix"], {
        visualKind: "comparison",
        columns: ["Interpretation", "Query forms", "History boundary"],
        common: "All five systems transformed dialogue into more than one retriever input.",
        different: "They differed in conversation window, explicit structure, and whether history became text, entities, co-occurrence, or transitions.",
        teams: [
          { name: "npatta01", values: ["DeepSeek V1 structured state", "Weighted BM25, field-aligned dense strings, deterministic b1_cos", "Multi-turn memory, current request, played-track facts"] },
          { name: "volart", values: ["Concise rewrite plus JSON entities", "Rewrite for lexical/dense; entities and played IDs for separate lanes", "Goal, latest request, and available history"] },
          { name: "niwatori", values: ["Source-specific safe text and learned encodings", "Lexical, dense, history/co-occurrence, and transition forms", "Recent text, full played IDs, and last track by source"] },
          { name: "swyoo", values: ["Current request, music context, and cached summary", "BM25, QEmb, and two-tower representations", "Recent listens and chat-derived aggregates"] },
          { name: "team2_s2", values: ["Conversation text plus source-specific item context", "BM25 conversation, live text, and item/CF branches", "Prior turns and last one, three, or all played tracks"] },
        ],
      }),
      slide("data-glossary", "Four places system knowledge can come from", "visual", ["data_knowledge_heading", "data_knowledge_glossary"], {
        visualKind: "mechanism",
        takeaway: "Reproducibility depends on separating recorded facts from generated artifacts and latent model associations.",
        stages: [
          { label: "Challenge records", detail: "Catalog, conversations, users, labels, and played history" },
          { label: "External structured data", detail: "Lyrics, identifiers, credits, or outside interaction records" },
          { label: "Generated artifacts", detail: "States, rewrites, descriptions, candidates, critiques, and repairs" },
          { label: "LLM world knowledge", detail: "Uncited associations available only inside model generation" },
          { label: "Verification boundary", detail: "What another record can independently reproduce or check" },
        ],
      }),
      slide("provenance-stacks", "How evidence provenance stacks up", "visual", [], {
        visualKind: "provenance",
        takeaway: "Recorded, generated, latent, and verified evidence have different reproducibility boundaries.",
        layers: provenanceLayers,
        teams: [
          { name: "npatta01", cells: [
            cell("present", "Official catalog, embeddings, conversations, users, and public labels", "Catalog + conversations"),
            cell("not-documented", "No external structured music dataset documented", "None"),
            cell("present", "Cached conversation state and artist known-for text", "State + known-for"),
            cell("partial", "Response-model associations were available but not independently recorded", "Response-model associations"),
            cell("partial", "Catalog IDs were resolved; no independent response fact checker was documented", "IDs only; no checker"),
          ] },
          { name: "volart", cells: [
            cell("present", "Official records, train co-occurrence, frequency, and MOVES priors", "Records + priors"),
            cell("not-documented", "No external structured music dataset documented", "None"),
            cell("present", "Rewrites, descriptions, response candidates, critiques, and edits", "Rewrites + critiques"),
            cell("partial", "Model associations could enter generated descriptions and drafts", "Model associations"),
            cell("partial", "Track IDs stayed fixed; structured musical-fact verification was not documented", "IDs fixed; facts unchecked"),
          ] },
          { name: "niwatori", cells: [
            cell("present", "Official challenge records", "Challenge records"),
            cell("present", "TalkPlayData-1 statistics", "TalkPlayData-1"),
            cell("partial", "Ten response drafts; no LLM retrieval rewrite documented", "10 drafts; no query rewrite"),
            cell("partial", "Response-model associations could enter the drafts", "Response-model associations"),
            cell("partial", "Mapped external IDs, duplicate audits, and OOF training; response fact checking not documented", "ID audits; response unchecked"),
          ] },
          { name: "swyoo", cells: [
            cell("present", "Official challenge records", "Challenge records"),
            cell("present", "LRCLIB, Genius, and MusicBrainz", "LRCLIB · Genius · MusicBrainz"),
            cell("present", "Summaries, themes, candidates, and repaired responses", "Summaries + repairs"),
            cell("partial", "Model predictions supplemented recorded facts", "Model predictions"),
            cell("present", "Theme, citation, and field-level validation with repair", "Checks + repair"),
          ] },
          { name: "team2_s2", cells: [
            cell("present", "Official catalog, conversations, users, labels, and embeddings", "Catalog + conversations"),
            cell("not-documented", "No external structured music dataset documented", "None"),
            cell("present", "Fact bundles, first-pass responses, and refinements", "Facts + responses"),
            cell("partial", "Gemini generation could add associations beyond the supplied facts", "Gemini associations"),
            cell("present", "Verified track facts were supplied to generation", "Verified facts"),
          ] },
        ],
      }),
      slide("data-matrix", "Common records, different knowledge boundaries", "matrix", ["data_knowledge_matrix", "data_knowledge_interpretation"], {
        visualKind: "comparison",
        columns: ["Recorded data", "Generated or latent knowledge", "Grounding boundary"],
        common: "Every reviewed system used official challenge data and persisted some model-generated artifacts.",
        different: "External datasets and the checks placed around model-authored musical claims varied substantially.",
        teams: [
          { name: "npatta01", values: ["Official catalog, embeddings, conversations/users, public labels", "Cached state and artist known-for text; response-model associations", "Catalog-resolved IDs; no independent response fact checker documented"], status: "limit" },
          { name: "volart", values: ["Official records plus train co-occurrence and frequency/MOVES priors", "Rewrites, descriptions, response candidates, critiques, and edits", "Track IDs held fixed; structured musical-fact verification not documented"], status: "limit" },
          { name: "niwatori", values: ["Official records plus TalkPlayData-1 statistics", "No LLM retrieval rewrite documented; ten response drafts", "Mapped external IDs, duplicate audits, and OOF training; response fact checking not documented"], status: "external" },
          { name: "swyoo", values: ["Official records plus LRCLIB, Genius, and MusicBrainz", "Summaries, themes, candidates, and repaired responses", "Broadest documented external fact path with field-level checks"], status: "verified" },
          { name: "team2_s2", values: ["Official catalog, conversations, users, labels, and embeddings", "Fact bundles, first-pass responses, and refinements", "Verified track facts supplied to generation; no external music dataset documented"], status: "verified" },
        ],
      }),
      slide("prompt-audit", "Prompt and file audit", "audit", ["query_evidence_details"]),
    ],
  },
  {
    slug: "retrieval",
    title: "Retrieval & ranking",
    question: "What candidates and features could the rankers actually see?",
    slides: [
      slide("cover", "Retrieval & ranking", "cover", []),
      slide("retriever-mechanism", "Many evidence lanes become one candidate boundary", "visual", [], {
        visualKind: "mechanism",
        takeaway: "A ranker can only rescue tracks that entered its candidate set; source diversity matters before feature richness does.",
        stages: [
          { label: "Query variants", detail: "Text, dense vectors, entities, history, and constraints" },
          { label: "Parallel sources", detail: "Lexical, semantic, collaborative, lookup, and transition lanes" },
          { label: "Candidate assembly", detail: "Union, late fusion, dedicated slots, or routing" },
          { label: "Feature computation", detail: "Per-source evidence, metadata, history, and agreement" },
          { label: "Final ordering", detail: "Learned ranker, selector, or deterministic fusion" },
        ],
      }),
      slide("retriever-matrix", "Same boundary, different retrieval evidence", "matrix", ["retrieval_heading", "retrieval_glossary", "retrieval_matrix"], {
        visualKind: "comparison",
        columns: ["Candidate sources", "History use", "Constraints"],
        common: "Every reviewed path combined multiple evidence sources before choosing final track IDs.",
        different: "Direct co-occurrence and transition lanes, history seeding, candidate union rules, and hard filters were not shared equally.",
        teams: [
          { name: "npatta01", values: ["BM25, multimodal ANN, CF/BPR centroids, discography, era lookup", "Accepted/referenced tracks anchor; rejected items demote or drop", "Hard track rejection, tag demotion, artist veto, soft era preference"], status: "limit" },
          { name: "volart", values: ["BM25, metadata dense, LLM-description dense, entities, train co-occurrence", "Played tracks seed co-occurrence and are excluded", "Dedicated entity/era slots and already-played exclusion"], status: "verified" },
          { name: "niwatori", values: ["Lexical, dense, co-occurrence/history, transition, and prior sources", "Full played history for co-occurrence; last track for transitions", "Source-specific safety and candidate handling"], status: "external" },
          { name: "swyoo", values: ["BM25, QEmb, two-tower, and metadata/demographic evidence", "Recent listens accompany current and summarized context", "Already-seen tracks excluded; cues stay soft; no general hard rejection documented"], status: "verified" },
          { name: "team2_s2", values: ["BM25 conversation, live text, CF/BPR, and item branches", "Last one, three, or all played tracks depending on source", "Played-track exclusion enforced; explicit rejection, era, popularity, and novelty rules not documented"], status: "verified" },
        ],
      }),
      slide("evidence-heatmap", "Which retrieval evidence each system could use", "visual", [], {
        visualKind: "heatmap",
        takeaway: "Candidate-source coverage determines which evidence can become a ranking feature downstream.",
        columns: evidenceColumns,
        teams: [
          { name: "npatta01", badge: "142 features", cells: [
            cell("present", "BM25 lexical retrieval"), cell("present", "Multimodal and metadata ANN retrieval"), cell("present", "CF/BPR centroid retrieval"),
            cell("not-documented", "No direct track co-occurrence source documented"), cell("not-documented", "No transition source documented"), cell("present", "Discography and era lookup branches"),
            cell("partial", "Artist known-for text, not a general generated-description lane"), cell("present", "Catalog and media metadata features"), cell("present", "Conversation-state and feedback features"),
            cell("present", "Cross-source agreement and routing features"), cell("partial", "Popularity and frequency evidence, without a dedicated prior source"),
          ] },
          { name: "volart", badge: "69 features", cells: [
            cell("present", "BM25 lexical retrieval"), cell("present", "Metadata dense retrieval"), cell("partial", "Played-track co-occurrence rather than a learned collaborative model"),
            cell("present", "Train co-occurrence source"), cell("not-documented", "No transition source documented"), cell("present", "Entity and era lookup slots"),
            cell("present", "LLM-generated track descriptions"), cell("present", "Metadata features"), cell("present", "Rewrite, entities, and played-history evidence"),
            cell("present", "RRF, source ranks, and agreement evidence"), cell("present", "Frequency and MOVES priors"),
          ] },
          { name: "niwatori", badge: "176 features", cells: [
            cell("present", "Lexical retrieval sources"), cell("present", "Dense learned retrieval sources"), cell("present", "History and collaborative evidence"),
            cell("present", "Full-history co-occurrence sources"), cell("present", "Last-track transition sources"), cell("partial", "Source-specific lookup evidence"),
            cell("not-documented", "No generated-description retrieval lane documented"), cell("present", "Track and source metadata"), cell("present", "Recent text and played-history signals"),
            cell("present", "Ordered-union, source, and agreement features"), cell("present", "Prior sources including TalkPlayData-1 statistics"),
          ] },
          { name: "swyoo", badge: "Count not established", cells: [
            cell("present", "BM25 lexical retrieval"), cell("present", "QEmb and two-tower dense retrieval"), cell("present", "Two-tower interaction evidence"),
            cell("partial", "Chat-derived aggregate behavior, not a dedicated co-occurrence lane"), cell("not-documented", "No direct transition source documented"), cell("partial", "External metadata and identifier lookups"),
            cell("partial", "Generated summaries and themes, not a documented generated track-description retriever"), cell("present", "Catalog, demographic, lyrics, and credit metadata"), cell("present", "Current request, summary, and recent-listen evidence"),
            cell("present", "Multi-source fusion and compatibility evidence"), cell("partial", "Popularity or demographic priors were available but exact submitted usage is bounded"),
          ] },
          { name: "team2_s2", badge: "37 features", cells: [
            cell("present", "BM25 conversation and live-text retrieval"), cell("present", "Dense text and item branches"), cell("present", "CF/BPR branches"),
            cell("partial", "Collaborative item evidence without a separately documented co-occurrence source"), cell("not-documented", "No transition source documented"), cell("partial", "Item and catalog lookup evidence"),
            cell("not-documented", "No generated-description retrieval lane documented"), cell("present", "Catalog and item metadata"), cell("present", "Conversation and played-track windows"),
            cell("present", "Source and fusion features"), cell("partial", "Some popularity evidence; explicit popularity and novelty rules not documented"),
          ] },
        ],
      }),
      slide("feature-glossary", "Feature-family glossary", "story", ["features_heading", "feature_glossary"]),
      slide("feature-matrix", "Feature families and validation lineage", "matrix", ["feature_matrix"]),
      slide("feature-inventories", "Complete feature inventories", "audit", ["feature_details"]),
    ],
  },
  {
    slug: "response",
    title: "Response generation",
    question: "How did a selected track become grounded, checked prose?",
    slides: [
      slide("cover", "Response generation", "cover", []),
      slide("overview", "A selected track still needs a response pipeline", "visual", ["response_heading", "response_explainer"], {
        visualKind: "mechanism",
        takeaway: "Multiple drafts help only when a documented selector, verifier, critic, or repair pass decides what survives.",
        stages: [
          { label: "Selected track ID", detail: "Recommendation identity is fixed before prose work" },
          { label: "Grounding bundle", detail: "Dialogue state, catalog facts, and verified external facts when available" },
          { label: "Candidate generation", detail: "One response or several sampled alternatives" },
          { label: "Quality control", detail: "Selection, verification, critique, repair, or polishing" },
          { label: "Final response", detail: "Grounded explanation with the selected track preserved" },
        ],
      }),
      slide("grounding-heatmap", "What grounded each response", "visual", ["response_matrix"], {
        visualKind: "comparison",
        takeaway: "Grounding strength depended on which facts reached generation and which claims were independently checkable.",
        columns: ["Candidates", "Grounding", "Selection / repair"],
        common: "All five systems generated response prose after recommendation IDs were selected.",
        different: "Candidate count alone was not the distinction; independent checking, selection, and repair determined whether alternatives added control.",
        teams: [
          { name: "npatta01", values: ["One response", "Latest state and selected-track metadata", "No independent selector, critic, or fact checker documented"], status: "limit" },
          { name: "volart", values: ["Three temperature-diverse candidates", "Selected IDs remain fixed", "Independent critic, selective rewrite, hardening, lexical pass"], status: "verified" },
          { name: "niwatori", values: ["Ten seeded candidates", "Selected track and conversation context", "Lexical-diversity selector chooses a whole record; not a factual critic"], status: "verified" },
          { name: "swyoo", values: ["Deterministic PAS proposals plus one PAS prediction", "Catalog/crawl facts and legal title pool", "Validate and repair themes/citations; no best-of-N critic"], status: "verified" },
          { name: "team2_s2", values: ["First-pass response then refinement", "Verified track-fact bundle", "Second Gemini Pro polishing pass"], status: "verified" },
        ],
      }),
      slide("control-heatmap", "How each response was selected, checked, or repaired", "visual", [], {
        visualKind: "control-lanes",
        takeaway: "Multiple drafts add control only when a documented selector, verifier, critic, or repair pass decides what survives.",
        columns: responseColumns,
        teams: [
          { name: "npatta01", cells: [cell("present", "Latest state and selected-track catalog metadata", "State + catalog"), cell("present", "One response draft", "1 draft"), cell("not-documented", "No independent selector documented", "None"), cell("not-documented", "No independent checker documented", "None"), cell("not-documented", "No repair pass documented", "None"), cell("not-documented", "No lexical-control pass documented", "None")] },
          { name: "volart", cells: [cell("present", "Selected recommendation IDs stayed fixed", "IDs fixed"), cell("present", "Three temperature-diverse candidates", "3 varied drafts"), cell("present", "Independent critic selected or rejected candidates", "Critic"), cell("partial", "Quality hardening, not a documented structured musical-fact verifier", "Quality hardening"), cell("present", "Selective rewrite and hardening", "Selective rewrite"), cell("present", "Lexical-diversity pass", "Lexical pass")] },
          { name: "niwatori", cells: [cell("present", "Selected track and conversation context", "Track + conversation"), cell("present", "Ten seeded candidates", "10 seeded drafts"), cell("present", "Lexical-diversity selection of a whole record", "Diversity selector"), cell("not-documented", "Selector was not a factual critic", "Not a factual critic"), cell("not-documented", "No repair pass documented", "None"), cell("present", "Lexical diversity was the selection objective", "Diversity objective")] },
          { name: "swyoo", cells: [cell("present", "Catalog and crawled facts with a legal title pool", "Catalog + crawls"), cell("present", "Deterministic PAS proposals plus one PAS prediction", "PAS set"), cell("partial", "Deterministic proposal path, not best-of-N critique", "No critic"), cell("present", "Theme and citation validation", "Theme-citation checks"), cell("present", "Unsupported content was repaired", "Evidence repair"), cell("partial", "Legal-title controls, not a lexical-diversity selector", "Legal-title control")] },
          { name: "team2_s2", cells: [cell("present", "Verified track-fact bundle", "Verified facts"), cell("present", "First response followed by refinement", "Draft + refinement"), cell("partial", "Gemini Pro refined the first response rather than independently selecting drafts", "Refinement, not selector"), cell("present", "Verified facts supplied before generation", "Verified bundle"), cell("partial", "Gemini Pro polished the first response; factual repair was not separately documented", "Polishing pass"), cell("not-documented", "No lexical-control pass documented", "None")] },
        ],
      }),
      slide("tradeoffs", "Generation, selection, repair, and trade-offs", "audit", ["response_walkthroughs", "response_tradeoffs"]),
    ],
  },
  {
    slug: "leaders",
    title: "Leading teams",
    question: "What did the leading public systems document differently?",
    slides: [
      slide("cover", "Leading teams", "cover", ["competitor_case_studies_heading"]),
      slide("volart-outcome", "volart · outcome, query, and data", "story", ["volart_heading", "volart_outcome"], { systemCard: LEADER_SYSTEM_CARDS.volart }),
      slide("volart-retrieval", "volart · retrieval and ranking", "visual", ["volart_diagram"]),
      slide("volart-response", "volart · response, comparison, and limits", "audit", ["volart_walkthrough", "volart_comparison", "volart_limits"]),
      slide("niwatori-outcome", "niwatori · outcome, query, and data", "story", ["niwatori_heading", "niwatori_outcome"], { systemCard: LEADER_SYSTEM_CARDS.niwatori }),
      slide("niwatori-retrieval", "niwatori · retrieval and ranking", "visual", ["niwatori_diagram"]),
      slide("niwatori-response", "niwatori · response, comparison, and limits", "audit", ["niwatori_walkthrough", "niwatori_comparison", "niwatori_limits"]),
      slide("swyoo-outcome", "swyoo · outcome, query, and data", "story", ["swyoo_heading", "swyoo_outcome"], { systemCard: LEADER_SYSTEM_CARDS.swyoo }),
      slide("swyoo-retrieval", "swyoo · retrieval and ranking", "visual", ["swyoo_diagram"]),
      slide("swyoo-response", "swyoo · response, comparison, and limits", "audit", ["swyoo_walkthrough", "swyoo_comparison", "swyoo_limits"]),
      slide("team2-outcome", "team2_s2 · outcome, query, and data", "story", ["team2_s2_heading", "team2_s2_outcome"], { systemCard: LEADER_SYSTEM_CARDS.team2_s2 }),
      slide("team2-retrieval", "team2_s2 · retrieval and ranking", "visual", ["team2_s2_diagram"]),
      slide("team2-response", "team2_s2 · response, comparison, and limits", "audit", ["team2_s2_walkthrough", "team2_s2_comparison", "team2_s2_limits"]),
    ],
  },
  {
    slug: "synthesis",
    title: "Synthesis & evidence",
    question: "What should the team preserve, reconsider, avoid, and credit?",
    slides: [
      slide("cover", "Synthesis & evidence", "cover", ["cross_team_heading"]),
      slide("matrix", "Cross-team synthesis", "matrix", ["cross_team_matrix"]),
      slide("decoder", "Decode three important rows", "visual", [], {
        visualKind: "matrix-decoder",
        concepts: [
          {
            term: "Reranker evidence breadth",
            definition: "Signals LightGBM can inspect for candidates that already reached it; richness means diverse decision evidence, not just more columns.",
            stages: ["Candidate in union", "Feature evidence", "LightGBM score"],
            had: ["142 documented features", "Branch ranks/scores and agreement", "Dense, multimodal, CF/BPR centroid, state, and catalog evidence"],
            lacked: ["Direct track co-occurrence sum/max/probability or lane membership", "Markov transition probability", "Candidate-producing learned-retriever rank/score", "Grounded generated-description similarity", "Stronger explicit behavior-derived priors"],
            why: "A reranker cannot use source evidence that was never generated or attached to a candidate.",
          },
          {
            term: "Full candidate union / late fusion",
            definition: "A full union keeps every deduplicated source candidate; late fusion keeps source evidence separate until a later scorer combines it.",
            stages: ["Up to 500 hits from each traced branch", "Filtered candidate union", "LightGBM final ordering"],
            had: ["Multiple deployed retrieval branches", "Per-branch candidate evidence", "LightGBM final ordering of the union"],
            lacked: ["Tracks never emitted by a deployed branch", "Tracks removed before the union", "A candidate-producing lane from the trained two-tower"],
            why: "Anything outside the ranker's union was unrecoverable, regardless of downstream model quality.",
          },
          {
            term: "Factual grounding",
            definition: "Response claims are constrained to facts traceable to the selected track, conversation state, catalog, or another verified record.",
            stages: ["Selected track", "Verified fact bundle", "Allowed claims", "Checker or repair", "Final response"],
            had: ["Selected track", "Latest conversation state", "Track and catalog metadata"],
            lacked: ["Independent structured fact checker", "Theme or citation validation", "Repair pass for unsupported claims", "Selection among multiple grounded drafts"],
            why: "Our response had grounded inputs, so coverage is Partial; it lacked independent verification and repair controls.",
          },
        ],
      }),
      slide("choices", "Preserve, reconsider, and avoid", "story", ["preserve_reconsider_avoid", "retrospective_choices_table"]),
      slide("lessons", "Transferable lessons and acknowledgements", "story", ["future_competition_lessons", "acknowledgements_heading", "acknowledgements"]),
      slide("evidence", "Caveats and complete evidence", "audit", ["caveats", "evidence_notes"]),
    ],
  },
];

export const LEGACY_ALIASES = new Map([
  ["outcome/summary", "outcome/cover"], ["outcome/official-result", "outcome/leaderboard-chart"], ["outcome/gap", "outcome/gap-chart"],
  ["query/comparison", "query/query-matrix"], ["query/data-knowledge", "query/data-matrix"], ["query/query-glossary", "query/lifecycle"],
  ["retrieval/retrievers", "retrieval/retriever-matrix"], ["retrieval/features", "retrieval/feature-glossary"], ["retrieval/feature-audit", "retrieval/feature-inventories"],
  ["response/pipelines", "response/overview"], ["response/author-volart", "response/tradeoffs"], ["response/niwatori-swyoo", "response/tradeoffs"], ["response/team2", "response/tradeoffs"],
  ["ours/system", "ours/cover"], ["ours/strengths", "ours/what-worked"],
  ["leaders/index", "leaders/cover"], ["leaders/volart", "leaders/volart-outcome"], ["leaders/niwatori", "leaders/niwatori-outcome"], ["leaders/swyoo", "leaders/swyoo-outcome"], ["leaders/team2", "leaders/team2-outcome"],
  ["synthesis/cross-team", "synthesis/cover"], ["synthesis/acknowledgements", "synthesis/lessons"], ["synthesis/caveats-evidence", "synthesis/evidence"],
  ["response/matrix", "response/grounding-heatmap"], ["response/overview", "response/overview"], ["response/tradeoffs", "response/tradeoffs"], ["query/prompt-audit", "query/prompt-audit"], ["ours/walkthrough", "ours/walkthrough"], ["ours/evaluation-mistake", "ours/evaluation-mistake"], ["ours/contributors", "ours/contributors"], ["synthesis/choices", "synthesis/choices"], ["synthesis/lessons", "synthesis/lessons"],
]);

export const resolveSlug = (slug) => LEGACY_ALIASES.get(slug) || slug;

export const DISCLOSURES = {
  section_directory: "Open the original chapter outline",
  how_scoring_works: "Open the composite-score formula",
  leaderboard_table: "Open exact values and repository links",
  gap_interpretation: "Open the exact score arithmetic and evidence boundary",
  lifecycle_heading: "Open the source-backed lifecycle introduction",
  lifecycle_map: "Open the complete lifecycle map",
  lifecycle_takeaway: "Open the original lifecycle takeaway",
  query_heading: "Open the query-audit heading",
  query_explainer: "Open definitions, qualifications, and sources",
  query_matrix: "Open the complete five-team query matrix",
  query_evidence_details: "Open prompt excerpts and the reviewed file inventory",
  data_knowledge_heading: "Open the data-provenance heading",
  data_knowledge_glossary: "Open definitions and evidence boundaries",
  data_knowledge_matrix: "Open the complete data and model-knowledge matrix",
  data_knowledge_interpretation: "Open the complete provenance interpretation",
  retrieval_heading: "Open the retrieval-audit heading",
  retrieval_glossary: "Open definitions and the candidate-set boundary",
  retrieval_matrix: "Open the complete retrieval matrix",
  feature_matrix: "Open the complete feature-family matrix",
  feature_details: "Open the per-team feature inventories",
  response_heading: "Open the response-audit heading",
  response_explainer: "Open the complete response-system explanation",
  response_matrix: "Open the complete response-generation matrix",
  own_system_walkthrough: "Open the complete submitted-system walkthrough",
  volart_outcome: "Open the reviewed volart evidence and sources",
  niwatori_outcome: "Open the reviewed niwatori evidence and sources",
  swyoo_outcome: "Open the reviewed swyoo evidence and sources",
  team2_s2_outcome: "Open the reviewed team2_s2 evidence and sources",
  evidence_notes: "Open the complete evidence notes",
};

const STYLE_START = "<!-- retrospective-deck-style:start -->";
const STYLE_END = "<!-- retrospective-deck-style:end -->";
const SCRIPT_START = "<!-- retrospective-deck-script:start -->";
const SCRIPT_END = "<!-- retrospective-deck-script:end -->";

const removeRange = (html, start, end) => {
  const pattern = new RegExp(`${start.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}[\\s\\S]*?${end.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\n?`, "g");
  return html.replace(pattern, "");
};

export function stripDeckInjection(html) {
  return removeRange(removeRange(html, STYLE_START, STYLE_END), SCRIPT_START, SCRIPT_END);
}

export function validateChapterMap(chapters, html) {
  const mappedIds = chapters.flatMap((chapter) => chapter.slides.flatMap((entry) => entry.blocks));
  const seen = new Set();
  for (const id of mappedIds) {
    if (seen.has(id)) throw new Error(`duplicate configured block: ${id}`);
    seen.add(id);
  }
  const renderedIds = [...html.matchAll(/data-artifact-block-id="([^"]+)"/g)].map((match) => match[1]);
  const renderedSet = new Set(renderedIds);
  if (renderedIds.length !== renderedSet.size) throw new Error("duplicate report block ID");
  if (renderedSet.has("title")) throw new Error("title must be represented by the portable page header");
  if (!html.includes('class="portable-page-header"')) throw new Error("missing portable page header for title block");
  const reportIds = ["title", ...renderedIds];
  const reportSet = new Set(reportIds);
  for (const id of mappedIds) if (!reportSet.has(id)) throw new Error(`missing configured block: ${id}`);
  for (const id of reportIds) if (!seen.has(id)) throw new Error(`unassigned report block: ${id}`);
  if (!html.includes('class="portable-block-stack"')) throw new Error("missing portable block stack");
  if (!html.includes('class="portable-sources"')) throw new Error("missing portable source list");
  if (!html.includes('id="data-analytics-portable-artifact-payload-source"')) throw new Error("missing artifact payload template");
  const slugs = new Set();
  for (const chapter of chapters) for (const entry of chapter.slides) {
    if (!PAGE_ARCHETYPES.has(entry.archetype)) throw new Error(`unknown page archetype: ${entry.archetype}`);
    const slug = `${chapter.slug}/${entry.slug}`;
    if (slugs.has(slug)) throw new Error(`duplicate slide slug: ${slug}`);
    slugs.add(slug);
  }
  return {
    mappedIds,
    reportIds,
    slugs: [...slugs],
    pageCount: slugs.size,
    chapterCounts: chapters.map((chapter) => chapter.slides.length),
  };
}

export const DECK_STYLE = `
#data-analytics-portable-reader{display:none!important}
#data-analytics-portable-fallback{display:block!important;visibility:visible!important;position:relative!important;width:100%!important;max-width:none!important;padding:0!important}
html.retrospective-deck-ready,html.retrospective-deck-ready body{height:100%;overflow:hidden}
.retrospective-deck{height:100dvh;display:grid;grid-template-rows:auto minmax(0,1fr) auto;background:var(--portable-canvas);color:var(--portable-ink)}
.deck-chrome{position:relative;z-index:20;background:color-mix(in srgb,var(--portable-canvas) 92%,transparent);backdrop-filter:blur(12px)}
.deck-topbar,.deck-footer{display:flex;min-width:0;align-items:center;gap:12px;min-height:56px;padding:8px clamp(12px,2.5vw,32px);border-color:var(--portable-border)}
.deck-topbar{border-bottom:1px solid var(--portable-border)}
.deck-footer{justify-content:space-between;border-top:1px solid var(--portable-border)}
.deck-footer .deck-button{max-width:min(38vw,360px);padding:6px 12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.deck-title{margin-right:auto;font-weight:750}.deck-breadcrumb{color:var(--portable-muted)}
.deck-chapter-rail{display:flex;gap:4px}.deck-chapter-button{display:grid;place-items:center;width:32px;height:32px;padding:0;border:1px solid var(--portable-border);border-radius:999px;background:var(--portable-surface);color:var(--portable-muted);cursor:pointer}.deck-chapter-button[aria-current="true"]{border-color:var(--portable-accent);background:var(--portable-accent);color:#fff}.deck-mobile-orientation{display:none}
.deck-button{min-width:44px;min-height:44px;border:1px solid var(--portable-border);border-radius:10px;background:var(--portable-surface);color:var(--portable-ink);cursor:pointer}
.deck-button:focus-visible,.deck-jump-item:focus-visible,.deck-slide:focus-visible,.deck-rail-button:focus-visible,summary:focus-visible{outline:3px solid var(--portable-accent);outline-offset:3px}
.deck-track{display:flex;min-width:0;overflow-x:auto;overflow-y:hidden;scroll-snap-type:x mandatory;scroll-behavior:smooth;overscroll-behavior-x:contain;scrollbar-width:none}
.deck-chapter{position:relative;flex:0 0 100%;min-width:0;height:100%;scroll-snap-align:start}
.deck-vertical{height:100%;overflow-y:auto;overflow-x:hidden;scroll-snap-type:y proximity;overscroll-behavior-y:contain}
.deck-vertical-rail{position:absolute;z-index:10;right:12px;top:50%;transform:translateY(-50%);display:grid;gap:7px;padding:9px;border:1px solid var(--portable-border);border-radius:999px;background:color-mix(in srgb,var(--portable-surface) 88%,transparent)}
.deck-rail-button{position:relative;display:grid;place-items:center;width:28px;height:28px;padding:0;border:1px solid var(--portable-muted);border-radius:999px;background:var(--portable-surface);color:var(--portable-muted);font-size:11px;cursor:pointer}
.deck-rail-button[aria-current="true"]{border-color:var(--portable-accent);background:var(--portable-accent);color:#fff}
.deck-rail-button::after{position:absolute;right:36px;width:max-content;max-width:240px;padding:5px 8px;border:1px solid var(--portable-border);border-radius:7px;background:var(--portable-surface);color:var(--portable-ink);content:attr(data-label);font-size:12px;opacity:0;pointer-events:none;transform:translateX(4px);transition:opacity .12s,transform .12s}.deck-rail-button:hover::after,.deck-rail-button:focus::after{opacity:1;transform:translateX(0)}
.deck-slide{min-height:100%;padding:clamp(20px,3vw,46px) clamp(78px,7vw,104px) clamp(20px,3vw,46px) clamp(16px,3vw,44px);scroll-snap-align:start;scroll-margin-top:12px}
.deck-slide-inner{width:min(1520px,100%);margin:0 auto;display:grid;gap:clamp(16px,2vw,28px)}
.deck-slide-heading{margin:0;font-size:clamp(22px,3vw,38px);line-height:1.12}.deck-question{margin:0;color:var(--portable-muted)}
.deck-page-copy{display:grid;min-width:0;align-content:center;gap:12px;max-width:78ch}.deck-page-copy .deck-slide-heading{font-size:clamp(30px,4vw,58px)}
.deck-visual{min-width:0;margin:0;border:1px solid color-mix(in srgb,var(--portable-border) 74%,transparent);border-radius:clamp(16px,2vw,28px);overflow:hidden;background:#101216;box-shadow:0 28px 80px rgba(0,0,0,.2)}
.deck-visual img{display:block;width:100%;height:auto;aspect-ratio:16/9;object-fit:cover}
.deck-slide--cover .deck-slide-inner{grid-template-columns:minmax(400px,.9fr) minmax(0,2fr);align-items:center;min-height:calc(100dvh - 190px)}
.deck-slide--cover .deck-page-copy{grid-column:1;grid-row:1}
.deck-slide--cover .deck-slide-heading{max-width:100%;font-size:clamp(42px,5vw,72px);letter-spacing:-.045em;overflow-wrap:normal}.deck-slide--cover .deck-question{font-size:clamp(16px,1.6vw,22px);line-height:1.5}
.deck-chapter-map{grid-column:2;grid-row:1;display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin:0;padding:0;list-style:none;counter-reset:chapter-page}
.deck-chapter-map li{display:grid;grid-template-columns:auto 1fr;gap:10px;align-items:start;min-height:78px;padding:14px;border:1px solid var(--portable-border);border-radius:14px;background:linear-gradient(145deg,color-mix(in srgb,var(--portable-accent) 9%,var(--portable-surface)),var(--portable-surface));counter-increment:chapter-page}
.deck-chapter-map li::before{content:counter(chapter-page);display:grid;place-items:center;width:28px;height:28px;border-radius:999px;background:var(--portable-accent);color:#fff;font-size:12px;font-weight:800}.deck-chapter-map span{font-weight:700;line-height:1.3}
.deck-flow{display:grid;gap:18px}.deck-flow-lane{display:grid;gap:10px;padding:16px;border:1px solid var(--portable-border);border-radius:16px;background:var(--portable-surface)}.deck-flow-lane h3{margin:0;font-size:16px}.deck-flow-lane ol{display:grid;grid-template-columns:repeat(var(--flow-count),minmax(0,1fr));gap:24px;margin:0;padding:0;list-style:none;counter-reset:flow-step}.deck-flow-step{position:relative;min-width:0;padding:13px;border:1px solid color-mix(in srgb,var(--portable-accent) 38%,var(--portable-border));border-radius:12px;background:color-mix(in srgb,var(--portable-accent) 7%,var(--portable-surface));overflow-wrap:anywhere;counter-increment:flow-step}.deck-flow-step::before{content:counter(flow-step);display:block;margin-bottom:6px;color:var(--portable-accent);font-size:12px;font-weight:850}.deck-flow-step:not(:last-child)::after{content:"→";position:absolute;top:50%;right:-19px;color:var(--portable-accent);font-size:20px;font-weight:900;transform:translateY(-50%)}
.deck-flow-only .deck-slide-inner{min-height:calc(100dvh - 190px);grid-template-rows:auto minmax(0,1fr)}.deck-flow-only .deck-flow{align-self:center}.deck-flow-only .deck-flow-step{display:grid;min-height:128px;align-content:center;font-size:clamp(15px,1.2vw,18px);line-height:1.4}
.deck-mechanism{display:grid;gap:22px;align-self:center}.deck-mechanism-stages{display:grid;grid-template-columns:repeat(var(--stage-count),minmax(0,1fr));gap:26px;margin:0;padding:0;list-style:none;counter-reset:mechanism-stage}.deck-mechanism-stage{position:relative;display:grid;align-content:center;min-height:150px;padding:18px;border:1px solid var(--portable-border);border-top:5px solid var(--stage-color);border-radius:14px;background:var(--portable-surface);counter-increment:mechanism-stage}.deck-mechanism-stage::before{content:counter(mechanism-stage);margin-bottom:10px;color:var(--stage-color);font-size:13px;font-weight:900}.deck-mechanism-stage:not(:last-child)::after{content:"→";position:absolute;top:50%;right:-21px;color:var(--portable-accent);font-size:22px;font-weight:900;transform:translateY(-50%)}.deck-mechanism-stage h3{margin:0 0 8px;font-size:clamp(16px,1.35vw,20px)}.deck-mechanism-stage p{margin:0;color:var(--portable-muted);font-size:14px;line-height:1.5}.deck-takeaway{margin:0;padding:14px 18px;border-left:5px solid #d89a2b;border-radius:10px;background:color-mix(in srgb,#d89a2b 10%,var(--portable-surface));font-size:clamp(15px,1.15vw,18px);line-height:1.5}.deck-takeaway strong{display:block;margin-bottom:3px;color:#a96f09;font-size:12px;letter-spacing:.05em;text-transform:uppercase}
.deck-diagnosis{display:grid;gap:18px;min-width:0}.deck-diagnosis ol,.deck-diagnosis ul{margin:0;padding:0;list-style:none}.deck-diagnosis h3,.deck-diagnosis h4{margin:0}.deck-diagnosis li{min-width:0;overflow-wrap:anywhere}
.deck-evidence-boundary{display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center;padding:10px 12px;border:1px solid var(--portable-border);border-radius:12px;background:color-mix(in srgb,var(--portable-accent) 7%,var(--portable-surface));color:var(--portable-muted);font-size:12px;line-height:1.4}.deck-pinned-badge{display:inline-flex;width:max-content;padding:4px 9px;border:1px solid var(--portable-accent);border-radius:999px;color:var(--portable-accent);font-size:10px;font-weight:900;letter-spacing:.035em}
.deck-confidence-label{display:inline-flex!important;width:max-content;margin-bottom:7px;padding:3px 7px;border:1px solid currentColor;border-radius:999px;color:var(--portable-muted);font-size:9px!important;font-weight:900;line-height:1.1!important;letter-spacing:.06em;text-transform:uppercase}.deck-confidence-label[data-confidence="verified"]{color:#15945b!important}.deck-confidence-label[data-confidence="likely"]{color:#a66b08!important}.deck-confidence-label[data-confidence="unknown"]{color:var(--portable-muted)!important}
.deck-score-findings{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin:0;padding:0;list-style:none}.deck-score-finding{display:grid;gap:9px;min-height:120px;align-content:center;padding:16px;border:1px solid var(--portable-border);border-top:5px solid var(--portable-accent);border-radius:14px;background:var(--portable-surface)}.deck-score-finding h3{margin:0;font-size:18px}.deck-score-finding span{color:var(--portable-muted)}
.deck-system-card{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:0}.deck-system-field{min-width:0;padding:14px;border:1px solid var(--portable-border);border-top:4px solid var(--portable-accent);border-radius:12px;background:var(--portable-surface);overflow-wrap:anywhere}.deck-system-field[data-system-field="limit"]{border-top-color:#c98612}.deck-system-field dt{margin:0 0 6px;color:var(--portable-accent);font-size:10px;font-weight:900;letter-spacing:.05em;text-transform:uppercase}.deck-system-field[data-system-field="limit"] dt{color:#95600a}.deck-system-field dd{margin:0;color:var(--portable-muted);font-size:13px;line-height:1.4}.deck-system-field[data-system-field="result"] dd{color:var(--portable-ink);font-weight:800;font-variant-numeric:tabular-nums}
.deck-bottleneck{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:14px;counter-reset:bottleneck}.deck-bottleneck-stage,.deck-feature-family,.deck-boundary-column,.deck-confidence-column{min-width:0;padding:16px;border:1px solid var(--portable-border);border-radius:14px;background:var(--portable-surface)}.deck-bottleneck-stage{display:grid;gap:10px;align-content:start;counter-increment:bottleneck}.deck-bottleneck-stage::before{content:counter(bottleneck);color:var(--portable-accent);font-size:12px;font-weight:900}.deck-bottleneck-stage h3{font-size:15px}.deck-loss{padding:9px 11px;border-left:5px solid #c98612;border-radius:9px;background:color-mix(in srgb,#c98612 12%,var(--portable-surface));font-size:12px;line-height:1.35}
.deck-wiring{display:grid;grid-template-columns:minmax(0,1fr) minmax(160px,.5fr) minmax(0,1fr);gap:16px}.deck-wiring>section{display:grid;gap:9px;align-content:start}.deck-wiring>section>ol{display:grid;gap:7px}.deck-wiring-source li,.deck-wiring-target li{padding:8px 10px;border:1px solid var(--portable-border);border-radius:9px;background:var(--portable-surface);font-size:12px}.deck-wiring-link{padding:7px 9px;border:2px solid var(--portable-border);border-radius:9px;background:var(--portable-surface);font-size:11px;line-height:1.3}.deck-wiring-link[data-link-kind="direct"]{border-color:#15945b}.deck-wiring-link[data-link-kind="soft"]{border-style:dashed;border-color:#c98612}.deck-wiring-link[data-link-kind="feature-only"]{border-style:dotted;border-color:#6f54c7}
.deck-feature-map{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.deck-feature-family{display:grid;grid-template-columns:1fr auto;gap:9px}.deck-feature-family>.deck-confidence-label{grid-column:1/-1}.deck-feature-family h3{font-size:16px}.deck-feature-family>span:last-child{grid-column:1/-1;color:var(--portable-muted);font-size:13px;line-height:1.4}.deck-feature-badge{align-self:start;padding:3px 7px;border:1px solid var(--portable-accent);border-radius:999px;color:var(--portable-accent);font-size:10px;font-weight:800}
.deck-boundary-map,.deck-confidence-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}.deck-boundary-column,.deck-confidence-column{display:grid;gap:11px}.deck-boundary-column>ul,.deck-confidence-column>ul{display:grid;gap:7px}.deck-boundary-column li,.deck-confidence-column li{position:relative;padding-left:15px;color:var(--portable-muted);font-size:12px;line-height:1.35}.deck-boundary-column li::before,.deck-confidence-column li::before{position:absolute;left:0;content:"•";color:var(--portable-accent)}.deck-boundary-column[data-boundary="limited"]{border-top:5px solid #c98612}.deck-boundary-column[data-boundary="present"]{border-top:5px solid #15945b}
.deck-confidence{display:grid;gap:14px}.deck-confidence-column[data-confidence="verified"]{border-top:5px solid #15945b}.deck-confidence-column[data-confidence="likely"]{border-top:5px solid #c98612}.deck-confidence-column[data-confidence="unknown"]{border-top:5px solid var(--portable-muted)}.deck-response-control{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:18px}.deck-response-control>li{position:relative;padding:12px;border:1px solid var(--portable-border);border-radius:12px;background:var(--portable-surface)}.deck-response-control>li:not(:last-child)::after{position:absolute;top:50%;right:-15px;content:"→";color:var(--portable-accent);font-weight:900;transform:translateY(-50%)}.deck-response-control h3{margin-bottom:6px;font-size:14px}.deck-response-control span{color:var(--portable-muted);font-size:11px;line-height:1.35}
.deck-belief-timeline,.deck-failure-taxonomy{display:grid;gap:9px}.deck-belief-timeline>ol,.deck-failure-taxonomy>ol{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.deck-belief-timeline li,.deck-failure-taxonomy li{padding:10px 12px;border:1px solid var(--portable-border);border-radius:11px;background:var(--portable-surface)}.deck-belief-timeline h4,.deck-failure-taxonomy h4{margin-bottom:5px;font-size:12px}.deck-belief-timeline span,.deck-failure-taxonomy span{color:var(--portable-muted);font-size:10px;line-height:1.3}.deck-failure-taxonomy span{display:inline-block;margin-top:4px;padding:2px 6px;border:1px solid currentColor;border-radius:999px}
.deck-comparison{display:grid;gap:10px}.deck-comparison-columns,.deck-team-row{display:grid;grid-template-columns:minmax(115px,.55fr) repeat(3,minmax(0,1fr));gap:14px}.deck-comparison-columns{padding:0 16px;color:var(--portable-muted);font-size:11px;font-weight:800;letter-spacing:.04em;text-transform:uppercase}.deck-team-row{padding:14px 16px;border:1px solid var(--portable-border);border-left:5px solid var(--team-color);border-radius:12px;background:var(--portable-surface)}.deck-team-row h3{margin:0;font-size:16px}.deck-team-value{display:grid;gap:4px;color:var(--portable-muted);font-size:13px;line-height:1.42}.deck-team-value::before{content:attr(data-label);display:none;color:var(--portable-ink);font-size:10px;font-weight:800;letter-spacing:.04em;text-transform:uppercase}.deck-team-status{display:inline-flex;width:max-content;margin-top:7px;padding:3px 8px;border:1px solid currentColor;border-radius:999px;color:var(--portable-muted);font-size:10px;font-weight:800;text-transform:uppercase}.deck-team-status--verified{color:#19724d}.deck-team-status--external{color:#176e9e}.deck-team-status--limit{color:#9a6810}.deck-common-different{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:6px}.deck-synthesis-card{padding:14px 16px;border-left:5px solid var(--synthesis-color);border-radius:11px;background:var(--portable-surface);font-size:14px;line-height:1.5}.deck-synthesis-card strong{display:block;margin-bottom:4px;color:var(--portable-ink)}
.deck-team-grid{display:grid;gap:12px;min-width:0}.deck-team-grid table{width:100%;table-layout:fixed;border-collapse:separate;border-spacing:5px}.deck-team-grid caption{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}.deck-team-grid th,.deck-team-grid td{min-width:0;overflow-wrap:anywhere}.deck-team-grid thead th{padding:0 4px 5px;color:var(--portable-muted);font-size:9px;line-height:1.18;letter-spacing:.025em;text-align:center;text-transform:uppercase}.deck-team-grid thead th:first-child{width:128px;text-align:left}.deck-team-grid tbody th{padding:10px;border-left:5px solid var(--team-color);border-radius:10px;background:var(--portable-surface);font-size:14px;text-align:left}.deck-team-grid td{height:52px;padding:6px;border:1px solid var(--portable-border);border-radius:9px;background:var(--portable-surface);color:var(--portable-muted);font-size:10px;line-height:1.25;text-align:center;vertical-align:middle}.deck-grid-cell{display:grid;place-items:center;gap:4px}.deck-status-mark{display:inline-grid;place-items:center;width:24px;height:24px;border:2px solid currentColor;border-radius:7px;font-size:12px;font-weight:900}.deck-team-grid [data-status="present"]{color:#147a50;background:color-mix(in srgb,#15945b 14%,var(--portable-surface))}.deck-team-grid [data-status="partial"]{color:#95600a;background:color-mix(in srgb,#c98612 14%,var(--portable-surface))}.deck-team-grid [data-status="not-documented"]{color:var(--portable-muted);background:color-mix(in srgb,var(--portable-muted) 8%,var(--portable-surface))}.deck-team-grid [data-status="present"] .deck-status-mark::before{content:"✓"}.deck-team-grid [data-status="partial"] .deck-status-mark::before{content:"◐"}.deck-team-grid [data-status="not-documented"] .deck-status-mark::before{content:"—"}.deck-grid-cell-label{font-weight:700}.deck-evidence-heatmap .deck-grid-cell-label{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}.deck-feature-count{display:block;margin-top:4px;color:var(--portable-muted);font-size:9px;font-weight:750;line-height:1.2}.deck-control-lanes thead th:first-child{width:132px}.deck-control-lanes td{height:68px}.deck-control-lanes .deck-status-mark{width:20px;height:20px;font-size:10px}
.deck-provenance-stack{display:grid;gap:9px}.deck-provenance-head{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:7px;padding:0 13px 0 18px;color:var(--portable-muted);font-size:9px;font-weight:850;line-height:1.15;letter-spacing:.025em;text-align:center;text-transform:uppercase}.deck-provenance-team{padding:11px 13px;border:1px solid var(--portable-border);border-left:5px solid var(--team-color);border-radius:12px;background:var(--portable-surface)}.deck-provenance-team h3{margin:0 0 8px;font-size:15px}.deck-provenance-team ol{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:7px;margin:0;padding:0;list-style:none}.deck-provenance-layer{min-width:0;padding:8px;border:1px solid currentColor;border-radius:9px;font-size:10px;line-height:1.3}.deck-provenance-layer[data-status="present"]{color:#147a50;background:color-mix(in srgb,#15945b 12%,var(--portable-surface))}.deck-provenance-layer[data-status="partial"]{color:#95600a;background:color-mix(in srgb,#c98612 12%,var(--portable-surface))}.deck-provenance-layer[data-status="not-documented"]{color:var(--portable-muted);background:color-mix(in srgb,var(--portable-muted) 7%,var(--portable-surface))}.deck-provenance-layer strong{display:none;margin-bottom:4px;color:var(--portable-ink);font-size:9px;line-height:1.15;text-transform:uppercase}.deck-provenance-layer span{font-weight:650}
.deck-scoreboard{display:grid;align-self:start;grid-auto-rows:max-content;gap:6px;overflow-x:auto}.deck-score-header,.deck-score-row{display:grid;grid-template-columns:34px minmax(125px,1.25fr) minmax(130px,1fr) repeat(4,minmax(76px,.62fr));gap:12px;align-items:center;min-width:820px}.deck-score-header{padding:0 14px 5px;color:var(--portable-muted);font-size:10px;font-weight:800;letter-spacing:.04em;text-transform:uppercase}.deck-score-row{min-height:58px;padding:9px 14px;border:1px solid var(--portable-border);border-left:5px solid var(--score-color);border-radius:11px;background:var(--portable-surface)}.deck-score-rank{font-size:12px;font-weight:900}.deck-score-team{font-size:16px;font-weight:850}.deck-score-value{font-variant-numeric:tabular-nums;text-align:right}.deck-score-composite{position:relative;isolation:isolate;padding:7px 9px;border-radius:7px;overflow:hidden;text-align:right}.deck-score-composite::before{position:absolute;z-index:-1;inset:0 auto 0 0;width:var(--score-width);background:color-mix(in srgb,var(--score-color) 28%,transparent);content:""}
.deck-slide--story .deck-slide-inner{gap:clamp(24px,3vw,40px)}.deck-slide.deck-slide--story .portable-markdown{width:100%;max-width:1120px;font-size:clamp(17px,1.35vw,20px);line-height:1.65}.deck-slide--story .portable-markdown p{margin-block:0 1.15em}.deck-slide--story .portable-markdown a{font-weight:650}.deck-slide--story .portable-page-header,.deck-slide--story .portable-content-card{width:100%;max-width:1120px}.deck-slide--story .deck-question{font-size:clamp(15px,1.15vw,18px)}
.deck-slide--visual .deck-visual{max-width:1100px}.deck-slide--matrix .portable-content-card,.deck-slide--audit .portable-content-card{width:100%;max-width:none}
.deck-slide--matrix table{width:100%;table-layout:auto}.deck-slide--matrix th,.deck-slide--matrix td{white-space:normal;overflow-wrap:anywhere;vertical-align:top}
[id="synthesis/matrix"] [data-artifact-block-id],[id="synthesis/matrix"] .portable-content-card,[id="synthesis/matrix"] .portable-markdown,[id="synthesis/matrix"] .portable-table-scroll{width:100%;max-width:none}[id="synthesis/matrix"] table{table-layout:fixed}
.deck-slide--matrix .portable-table-scroll:has(.deck-prose-matrix){overflow:visible;border:0}.deck-prose-matrix{display:block!important;width:100%;font-size:14px!important}.deck-prose-matrix thead{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}.deck-prose-matrix tbody{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.deck-prose-matrix tbody tr{display:block;min-width:0;padding:4px 16px;border:1px solid var(--portable-border);border-radius:15px;background:var(--portable-surface)}.deck-prose-matrix tbody td{display:grid;grid-template-columns:minmax(130px,.34fr) minmax(0,1fr);gap:12px;width:100%;padding:11px 0;border-bottom:1px solid var(--portable-border);font-size:14px!important;line-height:1.45}.deck-prose-matrix tbody td:last-child{border-bottom:0}.deck-prose-matrix tbody td::before{content:attr(data-column-label);color:var(--portable-muted);font-size:11px;font-weight:750;letter-spacing:.035em;text-transform:uppercase}.deck-prose-matrix tbody td:first-child{font-weight:850;font-size:16px!important}.deck-prose-matrix tbody td:first-child::before{align-self:center}
.deck-embedded-document{display:block;width:100%;min-width:0;overflow:visible}.deck-embedded-document[hidden]{display:none}.portable-custom-html>iframe[hidden]{display:none!important}
.deck-slide .portable-page-header{position:static;width:auto;height:auto;min-height:0;margin:0;padding:0;border:0;background:transparent}
.deck-slide .portable-block-stack{display:contents}.deck-slide .portable-markdown{max-width:900px}
.deck-slide .portable-content-card,.deck-slide .portable-metric-card{box-shadow:none}
.deck-progressive .deck-slide-inner{grid-template-columns:1fr}.deck-progressive [data-artifact-block-id]{display:contents}.deck-insight-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;width:100%}.deck-insight-card{min-width:0;border:1px solid var(--portable-border);border-radius:14px;background:var(--portable-surface);overflow:clip}.deck-insight-card>summary{display:grid;gap:7px;min-height:118px;padding:16px 18px;cursor:pointer;list-style:none}.deck-insight-card>summary::-webkit-details-marker{display:none}.deck-insight-title{color:var(--portable-accent);font-size:clamp(16px,1.25vw,19px);font-weight:850}.deck-insight-lede{color:var(--portable-muted);font-size:14px;line-height:1.45}.deck-insight-card>summary::after{content:"Open detail +";align-self:end;color:var(--portable-accent);font-size:12px;font-weight:800}.deck-insight-card[open]>summary::after{content:"Close detail −"}.deck-insight-detail{margin:0;padding:0 18px 18px;border-top:1px solid var(--portable-border);font-size:14px;line-height:1.55}.deck-insight-detail strong:first-child{display:none}.deck-progressive .portable-markdown{display:contents}.deck-progressive .portable-content-card{display:contents}.deck-status{font-weight:800;text-align:center}.deck-status::before{display:inline-block;min-width:112px;padding:5px 10px;border:1px solid currentColor;border-radius:999px}.deck-status--yes{color:#19724d}.deck-status--yes::before{content:"Yes";background:color-mix(in srgb,#15945b 16%,transparent)}.deck-status--partial{color:#8b5b08}.deck-status--partial::before{content:"Partial";background:color-mix(in srgb,#c98612 16%,transparent)}.deck-status--missing{color:var(--portable-muted)}.deck-status--missing::before{content:"Not documented";background:color-mix(in srgb,var(--portable-muted) 10%,transparent)}.deck-status-label{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.deck-disclosure{border:1px solid var(--portable-border);border-radius:12px;background:var(--portable-surface);overflow:clip}
.deck-disclosure>summary{min-height:48px;padding:14px 18px;cursor:pointer;color:var(--portable-accent);font-weight:700}
.deck-disclosure:not([open])>:not(summary){display:none!important}
.deck-disclosure>[data-artifact-block-id]{border:0;border-radius:0}
.deck-source-list{margin-top:18px}.deck-source-list>.deck-disclosure{width:100%}#data-analytics-portable-fallback>.portable-sources,.deck-source-list>.portable-sources{display:block!important}
.deck-jump{position:fixed;inset:0;z-index:50;display:none;place-items:center;padding:20px;background:rgba(15,23,42,.72)}
.deck-jump[data-open="true"]{display:grid}.deck-jump-panel{width:min(720px,100%);max-height:min(720px,88dvh);overflow:auto;padding:18px;border:1px solid var(--portable-border);border-radius:16px;background:var(--portable-surface)}
.deck-jump-input{width:100%;min-height:46px;padding:10px 12px;border:1px solid var(--portable-border);border-radius:9px;background:var(--portable-canvas);color:var(--portable-ink)}
.deck-jump-list{display:grid;gap:8px;margin-top:12px}.deck-jump-item{width:100%;min-height:48px;padding:10px 12px;border:0;border-radius:9px;background:var(--portable-surface-subtle);color:var(--portable-ink);text-align:left;cursor:pointer}
.deck-live,.deck-skip{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}.deck-skip:focus{position:fixed;top:8px;left:8px;z-index:80;width:auto;height:auto;clip:auto;padding:10px;background:var(--portable-surface)}
html[data-deck-view="linear"],html[data-deck-view="linear"] body{height:auto;overflow:auto}
html[data-deck-view="linear"] .retrospective-deck{height:auto;display:block}html[data-deck-view="linear"] .deck-track{display:block;overflow:visible}html[data-deck-view="linear"] .deck-chapter,html[data-deck-view="linear"] .deck-slide{height:auto;min-height:0}html[data-deck-view="linear"] .deck-vertical{height:auto;overflow:visible}html[data-deck-view="linear"] .deck-vertical-rail{display:none}html[data-deck-view="linear"] .deck-disclosure>summary{display:none}html[data-deck-view="linear"] .deck-disclosure>[data-artifact-block-id]{display:block!important}html[data-deck-view="linear"] .deck-insight-grid{display:block}html[data-deck-view="linear"] .deck-insight-card{border:0;background:transparent;overflow:visible}html[data-deck-view="linear"] .deck-insight-card>summary{display:none}html[data-deck-view="linear"] .deck-insight-detail{display:block!important;margin:0 0 1em;padding:0;border:0}html[data-deck-view="linear"] .deck-insight-detail strong:first-child{display:inline}
@media(max-width:1100px){.deck-slide--cover .deck-slide-inner{grid-template-columns:1fr;min-height:0}.deck-slide--cover .deck-page-copy,.deck-chapter-map{grid-column:1;grid-row:auto}.deck-flow-lane ol,.deck-mechanism-stages{grid-template-columns:1fr;gap:22px}.deck-flow-step:not(:last-child)::after,.deck-mechanism-stage:not(:last-child)::after{content:"↓";top:auto;right:auto;bottom:-22px;left:50%;transform:translateX(-50%)}.deck-mechanism-stage{min-height:112px}.deck-comparison-columns{display:none}.deck-team-row{grid-template-columns:minmax(110px,.45fr) repeat(3,minmax(0,1fr))}.deck-prose-matrix tbody,.deck-insight-grid{grid-template-columns:1fr}.deck-flow-only .deck-slide-inner{min-height:0}}
@media(max-width:900px){.deck-bottleneck,.deck-feature-map,.deck-system-card{grid-template-columns:repeat(2,minmax(0,1fr))}.deck-wiring,.deck-boundary-map,.deck-confidence-grid{grid-template-columns:1fr}.deck-score-findings,.deck-response-control,.deck-belief-timeline>ol,.deck-failure-taxonomy>ol{grid-template-columns:repeat(2,minmax(0,1fr))}.deck-response-control>li::after{display:none}.deck-team-grid table,.deck-team-grid tbody{display:block}.deck-team-grid thead{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}.deck-team-grid tbody{display:grid;gap:12px}.deck-team-grid tr[data-team]{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px;padding:12px;border:1px solid var(--portable-border);border-left:5px solid var(--team-color);border-radius:13px;background:var(--portable-surface)}.deck-team-grid tbody th{grid-column:1/-1;padding:0 0 7px;border:0;border-bottom:1px solid var(--portable-border);border-radius:0;background:transparent}.deck-team-grid td{display:grid;grid-template-columns:minmax(80px,.6fr) minmax(0,1fr);gap:7px;align-items:center;height:auto;min-height:58px;text-align:left}.deck-team-grid td::before{content:attr(data-column);color:var(--portable-ink);font-size:9px;font-weight:850;letter-spacing:.025em;text-transform:uppercase}.deck-team-grid .deck-grid-cell{grid-template-columns:auto minmax(0,1fr);justify-items:start}.deck-evidence-heatmap .deck-grid-cell-label{position:static;width:auto;height:auto;overflow:visible;clip:auto;white-space:normal}.deck-provenance-head{display:none}.deck-provenance-team{padding:13px}.deck-provenance-team ol{grid-template-columns:1fr}.deck-provenance-layer{display:grid;grid-template-columns:minmax(105px,.45fr) minmax(0,1fr);gap:8px;align-items:center;min-height:52px}.deck-provenance-layer strong{display:block;margin:0}}
@media(max-width:600px){.deck-bottleneck,.deck-feature-map,.deck-score-findings,.deck-system-card,.deck-response-control,.deck-belief-timeline>ol,.deck-failure-taxonomy>ol{grid-template-columns:1fr}}
@media(max-width:700px){.deck-title,.deck-breadcrumb,.deck-progress,.deck-axis-help,.deck-chapter-rail{display:none}.deck-mobile-orientation{display:block;min-width:0;margin-right:auto;overflow:hidden;font-weight:650;text-overflow:ellipsis;white-space:nowrap}.deck-topbar,.deck-footer{min-height:60px;padding:8px 10px}.deck-slide{padding:18px 12px}.deck-vertical-rail{display:none}.portable-table-scroll{max-width:calc(100vw - 24px)}.deck-button{min-width:48px;min-height:48px}.deck-slide--cover .deck-slide-heading{font-size:clamp(36px,13vw,58px)}.deck-team-row,.deck-common-different{grid-template-columns:1fr}.deck-team-value::before{display:block}.deck-slide--matrix .portable-table-scroll{overflow-x:auto}.deck-slide--matrix .portable-table-scroll:has(.deck-prose-matrix){overflow:visible}.deck-prose-matrix tbody td{grid-template-columns:1fr;gap:4px}.deck-slide--audit .portable-markdown{columns:1}}
@media (pointer:coarse) and (min-width:701px) and (max-width:1279px){.deck-topbar{gap:6px;padding-inline:10px}.deck-title,.deck-breadcrumb,.deck-progress{display:none}.deck-mobile-orientation{display:block;min-width:0;margin-right:auto;overflow:hidden;font-weight:650;text-overflow:ellipsis;white-space:nowrap}.deck-chapter-rail{gap:3px}.deck-chapter-button,.deck-rail-button{width:44px;height:44px}.deck-vertical-rail{gap:3px;padding:6px}.deck-rail-button::after{right:50px}}
@media(prefers-reduced-motion:reduce){.deck-track,.deck-vertical{scroll-behavior:auto!important}}
@media(forced-colors:active){.deck-button,.deck-chapter-button,.deck-rail-button,.deck-disclosure,.deck-jump-panel{border:1px solid CanvasText}}
@media print{html,body{height:auto!important;overflow:visible!important}.deck-chrome,.deck-jump,.deck-skip,.deck-live,.deck-vertical-rail{display:none!important}.retrospective-deck,.deck-track,.deck-chapter,.deck-vertical,.deck-slide{display:block!important;height:auto!important;min-height:0!important;overflow:visible!important;scroll-snap-type:none!important}.deck-disclosure>summary{display:none!important}.deck-disclosure>[data-artifact-block-id],.deck-disclosure:not([open])>*:not(summary){display:block!important}.deck-insight-grid{display:block!important}.deck-insight-card{display:block!important;border:0!important;background:transparent!important;overflow:visible!important}.deck-insight-card>summary{display:none!important}.deck-insight-detail{display:block!important;margin:0 0 1em!important;padding:0!important;border:0!important}.deck-insight-detail strong:first-child{display:inline!important}}
`;

function runtimeMain(CONFIG) {
  const html = document.documentElement;
  const fallback = document.getElementById("data-analytics-portable-fallback");
  const stack = fallback?.querySelector(".portable-block-stack");
  const sources = fallback?.querySelector(".portable-sources");
  const pageHeader = fallback?.querySelector(":scope > .portable-page-header");
  if (!fallback || !stack || !sources || !pageHeader) return;
  const blocks = new Map([...stack.querySelectorAll(":scope > [data-artifact-block-id]")].map((node) => [node.dataset.artifactBlockId, node]));
  pageHeader.dataset.artifactBlockId = "title";
  blocks.set("title", pageHeader);

  const app = document.createElement("main");
  app.className = "retrospective-deck";
  app.setAttribute("aria-label", "Music-CRS retrospective deck");
  const skip = Object.assign(document.createElement("a"), { className: "deck-skip", href: "#outcome/summary", textContent: "Skip to current slide" });
  const live = Object.assign(document.createElement("div"), { className: "deck-live" });
  live.setAttribute("aria-live", "polite");
  live.setAttribute("aria-atomic", "true");
  const topbar = document.createElement("header");
  topbar.className = "deck-topbar deck-chrome";
  topbar.innerHTML = '<strong class="deck-title">Music-CRS retrospective</strong><span class="deck-mobile-orientation"></span><span class="deck-breadcrumb"></span><span class="deck-progress"></span><button class="deck-button" type="button" data-action="reading-path">Read retrospective</button><button class="deck-button" type="button" data-action="linear">Linear view</button><button class="deck-button" type="button" data-action="jump">Jump</button>';
  const chapterRail = document.createElement("nav");
  chapterRail.className = "deck-chapter-rail";
  chapterRail.setAttribute("aria-label", "Chapters");
  CONFIG.chapters.forEach((chapter, chapterIndex) => {
    const button = document.createElement("button");
    button.className = "deck-chapter-button";
    button.type = "button";
    button.dataset.go = `${chapter.slug}/${chapter.slides[0].slug}`;
    button.setAttribute("aria-label", chapter.title);
    button.title = chapter.title;
    button.textContent = String(chapterIndex + 1);
    chapterRail.append(button);
  });
  topbar.querySelector(".deck-title").after(chapterRail);
  const track = document.createElement("div");
  track.className = "deck-track";
  const footer = document.createElement("footer");
  footer.className = "deck-footer deck-chrome";
  footer.innerHTML = '<button class="deck-button" type="button" data-action="previous" aria-label="Previous">← Previous</button><span class="deck-axis-help">←/→ chapters · ↑/↓ depth</span><button class="deck-button" type="button" data-action="next" aria-label="Next">Next →</button>';
  const disclosure = (nodeOrNodes, label, disclosureFor) => {
    const nodes = Array.isArray(nodeOrNodes) ? nodeOrNodes : [nodeOrNodes];
    if (!label) return nodes[0];
    const details = document.createElement("details");
    details.className = "deck-disclosure";
    details.dataset.disclosureFor = disclosureFor || nodes[0].dataset.artifactBlockId;
    const summary = document.createElement("summary");
    summary.textContent = label;
    details.append(summary, ...nodes);
    return details;
  };
  const stageColors = ["#58aaf7", "#8570e6", "#24a88b", "#d89a2b", "#df7aa9"];
  const teamColors = ["#58aaf7", "#8570e6", "#24a88b", "#df7aa9", "#e28d43"];
  const confidenceLabels = { verified: "Verified", likely: "Likely contributor", unknown: "Unknown" };
  const labelDiagnosisClaim = (node, confidence) => {
    if (!confidenceLabels[confidence]) throw new Error(`Unknown diagnosis confidence: ${confidence}`);
    node.dataset.diagnosisClaim = "";
    node.dataset.confidence = confidence;
    const badge = document.createElement("span");
    badge.className = "deck-confidence-label";
    badge.dataset.confidence = confidence;
    badge.textContent = confidenceLabels[confidence];
    node.prepend(badge);
    return node;
  };
  const diagnosisClaim = (tagName, className, confidence) => {
    const node = document.createElement(tagName);
    if (className) node.className = className;
    return labelDiagnosisClaim(node, confidence);
  };
  const renderTakeaway = (takeaway) => {
    const confidence = typeof takeaway === "string" ? "unknown" : takeaway.confidence;
    const note = diagnosisClaim("aside", "deck-takeaway", confidence);
    const label = document.createElement("strong");
    label.textContent = "Takeaway";
    note.append(label, document.createTextNode(typeof takeaway === "string" ? takeaway : takeaway.text));
    return note;
  };
  const renderScoreFindings = () => {
    const findings = [
      ["Ranking / nDCG", "Most of the arithmetic gap"],
      ["LLM judge", "Another major share of the gap"],
      ["Catalog diversity", "Nearly neutral"],
      ["Lexical diversity", "Varied by team"],
    ];
    const list = document.createElement("ol");
    list.className = "deck-score-findings";
    list.setAttribute("aria-label", "Score-gap findings");
    findings.forEach(([title, detail]) => {
      const item = diagnosisClaim("li", "deck-score-finding", "verified");
      const heading = document.createElement("h3");
      heading.textContent = title;
      const text = document.createElement("span");
      text.textContent = detail;
      item.append(heading, text);
      list.append(item);
    });
    return list;
  };
  const renderGapFindings = () => {
    const findings = [
      ["Ranking + judge", "These terms dominate each leader's arithmetic advantage."],
      ["Catalog diversity", "The contribution is nearly neutral."],
      ["Evidence boundary", "The decomposition is arithmetic, not causal."],
    ];
    const list = document.createElement("ol");
    list.className = "deck-score-findings";
    list.setAttribute("aria-label", "Concise score-gap interpretation");
    findings.forEach(([title, detail]) => {
      const item = document.createElement("li");
      item.className = "deck-score-finding";
      const heading = document.createElement("h3");
      heading.textContent = title;
      const text = document.createElement("span");
      text.textContent = detail;
      item.append(heading, text);
      list.append(item);
    });
    return list;
  };
  const renderSystemCard = (fields) => {
    const card = document.createElement("dl");
    card.className = "deck-system-card";
    card.setAttribute("aria-label", "System summary");
    const labels = { result: "Result", query: "Query", knowledge: "Knowledge", retrieval: "Retrieval", response: "Response", limit: "Limit" };
    Object.entries(fields).forEach(([field, value]) => {
      const item = document.createElement("div");
      item.className = "deck-system-field";
      item.dataset.systemField = field;
      const term = document.createElement("dt");
      term.textContent = labels[field] || field;
      const description = document.createElement("dd");
      description.textContent = value;
      item.append(term, description);
      card.append(item);
    });
    return card;
  };
  const renderEvidenceBoundary = () => {
    const note = document.createElement("aside");
    note.className = "deck-evidence-boundary";
    const badge = document.createElement("span");
    badge.className = "deck-pinned-badge";
    badge.textContent = "Blind-B deployed evidence · 2ecc45a7";
    const caveat = document.createElement("span");
    caveat.textContent = "Repository documentation depth can bias “Not documented” comparisons; absence from reviewed sources is not proof of absence.";
    note.append(badge, caveat);
    return note;
  };
  const renderBottleneck = (entry) => {
    const list = document.createElement("ol");
    list.className = "deck-bottleneck";
    list.setAttribute("aria-label", "End-to-end information bottlenecks");
    entry.stages.forEach((stage) => {
      const item = diagnosisClaim("li", "deck-bottleneck-stage", "verified");
      const heading = document.createElement("h3");
      heading.textContent = stage;
      item.append(heading);
      entry.losses.filter(({ after }) => after === stage).forEach((loss) => {
        const note = diagnosisClaim("span", "deck-loss", loss.confidence);
        note.append(document.createTextNode(loss.label));
        item.append(note);
      });
      list.append(item);
    });
    return list;
  };
  const renderConstraintWiring = () => {
    const extracted = [
      "Current request",
      "Artist, album, track, and attribute facts",
      "Hard and soft exclusions",
      "Played-track acceptance",
      "Played-track rejection",
      "Played-track contrast",
      "Played-track sentiment",
      "Pinned played-track references",
      "Temporal and lyrical-theme constraints",
      "Resolved IDs and routing/profile fields",
    ];
    const consumers = [
      "Weighted BM25 clauses",
      "Field-aligned dense strings",
      "Audio and visual queries",
      "Anchor and user centroids",
      "Discography and era lookups",
      "Hard rejection, demotion, veto, and soft era handling",
      "LightGBM state, history, routing, rejection, and interaction features",
    ];
    const links = [
      ["Current request", "Weighted BM25 clauses", "direct"],
      ["Artist and attribute facts", "Field-aligned dense strings", "direct"],
      ["Attribute facts", "Audio and visual queries", "soft"],
      ["Played-track sentiment", "Anchor and user centroids", "soft"],
      ["Resolved artist and era", "Discography and era lookups", "direct"],
      ["Hard exclusions", "Hard rejection and artist veto", "direct"],
      ["Soft exclusions", "Tag demotion and soft era handling", "soft"],
      ["State and routing fields", "LightGBM features", "feature-only"],
    ];
    const group = (title, values, className) => {
      const section = document.createElement("section");
      section.className = className;
      const heading = document.createElement("h3");
      heading.textContent = title;
      const list = document.createElement("ol");
      values.forEach((value) => {
        const item = diagnosisClaim("li", "", "verified");
        item.append(document.createTextNode(value));
        list.append(item);
      });
      section.append(heading, list);
      return section;
    };
    const wiring = document.createElement("section");
    wiring.className = "deck-wiring";
    wiring.setAttribute("aria-label", "Extracted evidence wired to operational consumers");
    const linkGroup = document.createElement("section");
    linkGroup.className = "deck-wiring-links";
    const linkHeading = document.createElement("h3");
    linkHeading.textContent = "Verified connections";
    const linkList = document.createElement("ol");
    links.forEach(([from, to, kind]) => {
      const item = diagnosisClaim("li", "deck-wiring-link", "verified");
      item.dataset.linkKind = kind;
      item.append(document.createTextNode(`${from} → ${to}`));
      linkList.append(item);
    });
    linkGroup.append(linkHeading, linkList);
    wiring.append(group("Extracted state", extracted, "deck-wiring-source"), linkGroup, group("Actual consumers", consumers, "deck-wiring-target"));
    return wiring;
  };
  const renderFeatureMap = (families) => {
    const details = {
      "Retriever evidence": "Rank, score, presence, margin, ratio, percentile, z-score, source",
      "Semantic and multimodal": "b1_cos, Qwen metadata/lyrics, tags, CLAP audio, SigLIP visual",
      "Behavioral and lookup": "Anchor/user CF-BPR centroids, CF similarities, discography, era-popularity",
      Catalog: "Popularity, year, era, tags, artist, album, duration, culture, age affinity",
      "Conversation and state": "Request, intent, routing, rejection, temporal constraints, history, overlap",
      "Agreement and interactions": "Branch presence, best ranks, z-scores, percentiles, artist counts, cross-features",
    };
    const list = document.createElement("ol");
    list.className = "deck-feature-map";
    list.setAttribute("aria-label", "Six feature families in the 142-feature reranker");
    families.forEach((family, index) => {
      const item = diagnosisClaim("li", "deck-feature-family", "verified");
      const heading = document.createElement("h3");
      heading.textContent = family;
      const badge = document.createElement("span");
      badge.className = "deck-feature-badge";
      badge.textContent = index === 0 ? "142 total" : `Family ${index + 1}`;
      const detail = document.createElement("span");
      detail.textContent = details[family];
      item.append(heading, badge, detail);
      list.append(item);
    });
    return list;
  };
  const renderEvidenceBoundaries = () => {
    const columns = [
      ["Missing upstream source", ["Direct track co-occurrence lane", "Markov / sequential-transition lane", "Candidate-producing b1 lane", "Grounded generated-description retrieval"]],
      ["Consequent missing or limited feature", ["Direct co-occurrence probability and membership", "Transition probability", "Generated-description similarity", "Deliberate frequency priors"]],
      ["Present evidence", ["Dense similarity", "CF/BPR centroids", "Conversation state", "Rejection and temporal signals", "Metadata, popularity, and era", "Cross-source agreement"]],
    ];
    const list = document.createElement("ol");
    list.className = "deck-boundary-map";
    list.setAttribute("aria-label", "Upstream and downstream evidence boundaries");
    columns.forEach(([title, values], index) => {
      const item = document.createElement("li");
      item.className = "deck-boundary-column";
      item.dataset.boundary = index === 2 ? "present" : "limited";
      const heading = document.createElement("h3");
      heading.textContent = title;
      const evidence = document.createElement("ul");
      values.forEach((value) => {
        const row = diagnosisClaim("li", "", "verified");
        row.append(document.createTextNode(value));
        evidence.append(row);
      });
      item.append(heading, evidence);
      list.append(item);
    });
    return list;
  };
  const renderResponseControl = () => {
    const list = document.createElement("ol");
    list.className = "deck-response-control";
    list.setAttribute("aria-label", "Verified Blind-B response-control path");
    [
      ["Top-1 ID fixed", "Recommendation identity"],
      ["Grounded context", "Latest state plus XML-delimited catalog metadata"],
      ["One Qwen call", "Temperature zero · echo_retries=0"],
      ["Final response", "No independent selector, checker, critic, or repair"],
    ].forEach(([title, detail]) => {
      const item = diagnosisClaim("li", "", "verified");
      const heading = document.createElement("h3");
      heading.textContent = title;
      const text = document.createElement("span");
      text.textContent = detail;
      item.append(heading, text);
      list.append(item);
    });
    return list;
  };
  const renderConfidence = (confidence) => {
    const section = document.createElement("section");
    section.className = "deck-confidence";
    section.append(renderResponseControl());
    const grid = document.createElement("ol");
    grid.className = "deck-confidence-grid";
    grid.setAttribute("aria-label", "Confidence-ranked diagnosis");
    Object.entries(confidence).forEach(([level, claims]) => {
      const item = document.createElement("li");
      item.className = "deck-confidence-column";
      item.dataset.confidence = level;
      const heading = document.createElement("h3");
      heading.textContent = confidenceLabels[level];
      const list = document.createElement("ul");
      claims.forEach((claim) => {
        const row = diagnosisClaim("li", "", level);
        row.append(document.createTextNode(claim));
        list.append(row);
      });
      item.append(heading, list);
      grid.append(item);
    });
    section.append(grid);
    return section;
  };
  const renderBeliefTimeline = () => {
    const section = document.createElement("section");
    section.className = "deck-belief-timeline";
    const title = document.createElement("h3");
    title.textContent = "Belief update";
    const list = document.createElement("ol");
    [
      ["Before submission", "0.3844–0.4562 in-sample diagnostics encouraged confidence"],
      ["Evidence already available", "0.1970–0.2032 leakage-safe OOF results indicated weaker generalization"],
      ["Blind-B result", "0.2537 nDCG@20 and 3.30/5 judge score"],
      ["Post-competition review", "Candidate, constraint-execution, behavioral-evidence, and response-control gaps emerged"],
    ].forEach(([headingText, detail]) => {
      const item = diagnosisClaim("li", "", "verified");
      const heading = document.createElement("h4");
      heading.textContent = headingText;
      const text = document.createElement("span");
      text.textContent = detail;
      item.append(heading, text);
      list.append(item);
    });
    section.append(title, list);
    return section;
  };
  const renderFailureTaxonomy = () => {
    const section = document.createElement("section");
    section.className = "deck-failure-taxonomy";
    const title = document.createElement("h3");
    title.textContent = "Failure attribution · frequencies unknown";
    const list = document.createElement("ol");
    [
      "Relevant track never entered the candidate union",
      "Relevant track entered but was misranked",
      "Selected track was reasonable but its explanation was weak",
      "Recommendation and explanation were both weak",
    ].forEach((label) => {
      const item = diagnosisClaim("li", "", "unknown");
      const heading = document.createElement("h4");
      heading.textContent = label;
      const status = document.createElement("span");
      status.textContent = "Unknown frequency";
      item.append(heading, status);
      list.append(item);
    });
    section.append(title, list);
    return section;
  };
  const renderDiagnosis = (inner, entry) => {
    const root = document.createElement("section");
    root.className = `deck-diagnosis deck-diagnosis--${entry.diagnosisKind}`;
    root.setAttribute("aria-label", entry.title);
    root.append(renderEvidenceBoundary());
    if (entry.diagnosisKind === "bottleneck") root.append(renderBottleneck(entry));
    if (entry.diagnosisKind === "wiring") root.append(renderConstraintWiring());
    if (entry.diagnosisKind === "feature-map") root.append(renderFeatureMap(entry.featureFamilies));
    if (entry.diagnosisKind === "boundaries") root.append(renderEvidenceBoundaries());
    if (entry.diagnosisKind === "confidence") root.append(renderConfidence(entry.confidence), renderBeliefTimeline(), renderFailureTaxonomy());
    if (entry.diagnosisKind === "score") root.append(renderScoreFindings());
    if (entry.takeaway) root.append(renderTakeaway(entry.takeaway));
    inner.append(root);
  };
  const renderMechanism = (entry) => {
    const section = document.createElement("section");
    section.className = "deck-mechanism";
    section.setAttribute("aria-label", `${entry.title} mechanism`);
    const stages = document.createElement("ol");
    stages.className = "deck-mechanism-stages";
    stages.style.setProperty("--stage-count", String(entry.stages.length));
    entry.stages.forEach((stage, index) => {
      const item = document.createElement("li");
      item.className = "deck-mechanism-stage";
      item.style.setProperty("--stage-color", stageColors[index % stageColors.length]);
      const title = document.createElement("h3");
      title.textContent = stage.label;
      const detail = document.createElement("p");
      detail.textContent = stage.detail;
      item.append(title, detail);
      stages.append(item);
    });
    const takeaway = document.createElement("p");
    takeaway.className = "deck-takeaway";
    const label = document.createElement("strong");
    label.textContent = "Takeaway";
    const takeawayText = typeof entry.takeaway === "string" ? entry.takeaway : entry.takeaway.text;
    takeaway.append(label, document.createTextNode(takeawayText));
    section.append(stages, takeaway);
    return section;
  };
  const renderComparison = (entry) => {
    const section = document.createElement("section");
    section.className = "deck-comparison";
    section.setAttribute("aria-label", `${entry.title} team comparison`);
    const columns = document.createElement("div");
    columns.className = "deck-comparison-columns";
    columns.append(document.createElement("span"));
    entry.columns.forEach((column) => {
      const label = document.createElement("span");
      label.textContent = column;
      columns.append(label);
    });
    section.append(columns);
    entry.teams.forEach((team, index) => {
      const row = document.createElement("article");
      row.className = "deck-team-row";
      row.style.setProperty("--team-color", teamColors[index % teamColors.length]);
      const identity = document.createElement("div");
      const name = document.createElement("h3");
      name.textContent = team.name;
      identity.append(name);
      if (team.status) {
        const status = document.createElement("span");
        status.className = `deck-team-status deck-team-status--${team.status}`;
        status.textContent = team.status === "limit" ? "Limit" : team.status === "external" ? "External data" : "Verified path";
        identity.append(status);
      }
      row.append(identity);
      team.values.forEach((value, valueIndex) => {
        const cell = document.createElement("span");
        cell.className = "deck-team-value";
        cell.dataset.label = entry.columns[valueIndex];
        cell.textContent = value;
        row.append(cell);
      });
      section.append(row);
    });
    const synthesis = document.createElement("div");
    synthesis.className = "deck-common-different";
    [["Common", entry.common, "#24a88b"], ["Different", entry.different, "#d89a2b"]].forEach(([title, text, color]) => {
      const card = document.createElement("div");
      card.className = "deck-synthesis-card";
      card.style.setProperty("--synthesis-color", color);
      const heading = document.createElement("strong");
      heading.textContent = title;
      card.append(heading, document.createTextNode(text));
      synthesis.append(card);
    });
    section.append(synthesis);
    return section;
  };
  const statusText = { present: "Present", partial: "Partial", "not-documented": "Not documented" };
  const appendComparisonTakeaway = (section, takeaway) => {
    if (!takeaway) return section;
    const note = document.createElement("p");
    note.className = "deck-takeaway";
    const label = document.createElement("strong");
    label.textContent = "Takeaway";
    note.append(label, document.createTextNode(takeaway));
    section.append(note);
    return section;
  };
  const renderTeamGrid = (className, columns, teams, title) => {
    const section = document.createElement("section");
    section.className = `deck-team-grid ${className}`;
    const table = document.createElement("table");
    const caption = document.createElement("caption");
    caption.textContent = `${title} team comparison`;
    const head = document.createElement("thead");
    const headingRow = document.createElement("tr");
    const teamHeading = document.createElement("th");
    teamHeading.scope = "col";
    teamHeading.textContent = "Team";
    headingRow.append(teamHeading);
    columns.forEach((column) => {
      const heading = document.createElement("th");
      heading.scope = "col";
      heading.textContent = column;
      headingRow.append(heading);
    });
    head.append(headingRow);
    const body = document.createElement("tbody");
    teams.forEach((team, index) => {
      const row = document.createElement("tr");
      row.dataset.team = team.name;
      row.style.setProperty("--team-color", teamColors[index % teamColors.length]);
      const identity = document.createElement("th");
      identity.scope = "row";
      identity.textContent = team.name;
      if (team.badge) {
        const badge = document.createElement("span");
        badge.className = "deck-feature-count";
        badge.textContent = team.badge;
        identity.append(badge);
      }
      row.append(identity);
      team.cells.forEach((value, valueIndex) => {
        const cellNode = document.createElement("td");
        const column = columns[valueIndex];
        cellNode.dataset.column = column;
        cellNode.dataset.status = value.status;
        cellNode.setAttribute("aria-label", `${column}: ${statusText[value.status]}. ${value.label}`);
        cellNode.title = value.label;
        const content = document.createElement("span");
        content.className = "deck-grid-cell";
        const mark = document.createElement("span");
        mark.className = "deck-status-mark";
        mark.setAttribute("aria-hidden", "true");
        const shortLabel = document.createElement("span");
        shortLabel.className = "deck-grid-cell-label";
        shortLabel.textContent = className === "deck-evidence-heatmap"
          ? `${statusText[value.status]} · ${value.short}`
          : value.short;
        content.append(mark, shortLabel);
        cellNode.append(content);
        row.append(cellNode);
      });
      body.append(row);
    });
    table.append(caption, head, body);
    section.append(table);
    return section;
  };
  const renderTeamStacks = (className, layers, teams, title) => {
    const section = document.createElement("section");
    section.className = className;
    section.setAttribute("aria-label", `${title} team comparison`);
    const layerHeadings = document.createElement("div");
    layerHeadings.className = "deck-provenance-head";
    layerHeadings.setAttribute("aria-hidden", "true");
    layers.forEach((layer) => {
      const heading = document.createElement("span");
      heading.textContent = layer;
      layerHeadings.append(heading);
    });
    section.append(layerHeadings);
    teams.forEach((team, index) => {
      const card = document.createElement("article");
      card.className = "deck-provenance-team";
      card.dataset.team = team.name;
      card.style.setProperty("--team-color", teamColors[index % teamColors.length]);
      const heading = document.createElement("h3");
      heading.textContent = team.name;
      const stack = document.createElement("ol");
      team.cells.forEach((value, valueIndex) => {
        const layer = document.createElement("li");
        layer.className = "deck-provenance-layer";
        layer.dataset.status = value.status;
        layer.setAttribute("aria-label", `${layers[valueIndex]}: ${statusText[value.status]}. ${value.label}`);
        layer.title = value.label;
        const label = document.createElement("strong");
        label.textContent = layers[valueIndex];
        const shortLabel = document.createElement("span");
        shortLabel.textContent = value.short;
        layer.append(label, shortLabel);
        stack.append(layer);
      });
      card.append(heading, stack);
      section.append(card);
    });
    return section;
  };
  const renderHeatmap = ({ columns, teams, title, takeaway }) => appendComparisonTakeaway(renderTeamGrid("deck-evidence-heatmap", columns, teams, title), takeaway);
  const renderProvenance = ({ layers, teams, title, takeaway }) => appendComparisonTakeaway(renderTeamStacks("deck-provenance-stack", layers, teams, title), takeaway);
  const renderControlLanes = ({ columns, teams, title, takeaway }) => appendComparisonTakeaway(renderTeamGrid("deck-control-lanes", columns, teams, title), takeaway);

  for (const chapter of CONFIG.chapters) {
    const chapterNode = document.createElement("section");
    chapterNode.className = "deck-chapter";
    chapterNode.dataset.chapter = chapter.slug;
    chapterNode.setAttribute("aria-label", chapter.title);
    const vertical = document.createElement("div");
    vertical.className = "deck-vertical";
    const rail = document.createElement("nav");
    rail.className = "deck-vertical-rail";
    rail.setAttribute("aria-label", `${chapter.title} slides`);
    chapter.slides.forEach((entry, slideIndex) => {
      const slideNode = document.createElement("section");
      slideNode.className = `deck-slide deck-slide--${entry.archetype}`;
      if (entry.lanes?.length && entry.blocks.length === 0) slideNode.classList.add("deck-flow-only");
      slideNode.id = `${chapter.slug}/${entry.slug}`;
      slideNode.dataset.slug = slideNode.id;
      slideNode.dataset.pageIndex = String(slideIndex + 1);
      slideNode.tabIndex = -1;
      slideNode.setAttribute("aria-labelledby", `${chapter.slug}-${entry.slug}-title`);
      const inner = document.createElement("div");
      inner.className = "deck-slide-inner";
      const pageCopy = document.createElement("div");
      pageCopy.className = "deck-page-copy";
      const heading = document.createElement("h2");
      heading.className = "deck-slide-heading";
      heading.id = `${chapter.slug}-${entry.slug}-title`;
      heading.textContent = entry.title;
      const question = document.createElement("p");
      question.className = "deck-question";
      question.textContent = chapter.question;
      pageCopy.append(heading, question);
      inner.append(pageCopy);
      if (entry.diagnosisKind) renderDiagnosis(inner, entry);
      if (entry.scoreFindings) inner.append(renderGapFindings());
      if (entry.systemCard) inner.append(renderSystemCard(entry.systemCard));
      if (entry.visualKind === "mechanism") inner.append(renderMechanism(entry));
      if (entry.visualKind === "comparison" && entry.teams) inner.append(renderComparison(entry));
      if (entry.visualKind === "heatmap") inner.append(renderHeatmap(entry));
      if (entry.visualKind === "provenance") inner.append(renderProvenance(entry));
      if (entry.visualKind === "control-lanes") inner.append(renderControlLanes(entry));
      if (entry.archetype === "cover") {
        const map = document.createElement("ol");
        map.className = "deck-chapter-map";
        map.setAttribute("aria-label", `${chapter.title} page map`);
        chapter.slides.slice(1).forEach((page) => {
          const item = document.createElement("li");
          const label = document.createElement("span");
          label.textContent = page.title;
          item.append(label);
          map.append(item);
        });
        inner.append(map);
      }
      if (entry.lanes?.length) {
        const flow = document.createElement("section");
        flow.className = "deck-flow";
        flow.setAttribute("aria-label", `${entry.title} explanatory flow`);
        entry.lanes.forEach((lane) => {
          const laneNode = document.createElement("article");
          laneNode.className = "deck-flow-lane";
          const laneHeading = document.createElement("h3");
          laneHeading.textContent = lane.label;
          const steps = document.createElement("ol");
          steps.style.setProperty("--flow-count", String(lane.steps.length));
          lane.steps.forEach((step) => {
            const item = document.createElement("li");
            item.className = "deck-flow-step";
            item.textContent = step;
            steps.append(item);
          });
          laneNode.append(laneHeading, steps);
          flow.append(laneNode);
        });
        inner.append(flow);
      }
      if (entry.systemCard) {
        const disclosureFor = entry.blocks.at(-1);
        inner.append(disclosure(entry.blocks.map((blockId) => blocks.get(blockId)), CONFIG.disclosures[disclosureFor], disclosureFor));
      } else {
        for (const blockId of entry.blocks) inner.append(disclosure(blocks.get(blockId), CONFIG.disclosures[blockId]));
      }
      slideNode.append(inner);
      vertical.append(slideNode);
      const railButton = document.createElement("button");
      railButton.className = "deck-rail-button";
      railButton.type = "button";
      railButton.dataset.go = slideNode.id;
      railButton.dataset.label = entry.title;
      railButton.setAttribute("aria-label", `Go to ${entry.title}`);
      railButton.textContent = String(slideIndex + 1);
      rail.append(railButton);
    });
    chapterNode.append(vertical, rail);
    track.append(chapterNode);
  }

  const finalSlide = track.querySelector('[id="synthesis/evidence"] .deck-slide-inner');
  const sourceDetails = document.createElement("details");
  sourceDetails.className = "deck-disclosure deck-source-list";
  sourceDetails.innerHTML = "<summary>Open the complete source list</summary>";
  sourceDetails.append(sources);
  finalSlide.append(sourceDetails);
  app.append(skip, topbar, track, footer, live);
  stack.replaceWith(app);

  app.querySelectorAll(".deck-slide--matrix table").forEach((table) => {
    const headers = [...table.querySelectorAll("thead th")].map((header) => header.textContent.trim());
    const cells = [...table.querySelectorAll("tbody td")];
    const averageCellLength = cells.length ? cells.reduce((total, cell) => total + cell.textContent.trim().length, 0) / cells.length : 0;
    if (headers.length < 4 || averageCellLength < 45) return;
    table.classList.add("deck-prose-matrix");
    table.querySelectorAll("tbody tr").forEach((row) => {
      [...row.children].forEach((cell, index) => { cell.dataset.columnLabel = headers[index] || `Column ${index + 1}`; });
    });
  });

  const leaderboardDetails = document.querySelector('[id="outcome/leaderboard-table"] details[data-disclosure-for="leaderboard_table"]');
  const leaderboardTable = leaderboardDetails?.querySelector("table");
  if (leaderboardDetails && leaderboardTable) {
    const numericText = (cell) => cell.textContent.trim().match(/^-?\d+(?:\.\d+)?/)?.[0] || "—";
    const rows = [...leaderboardTable.querySelectorAll("tbody tr")].map((row) => {
      const cells = [...row.cells];
      return [cells[0].textContent.trim(), cells[1].textContent.trim(), ...cells.slice(2, 7).map(numericText)];
    });
    const composites = rows.map((row) => Number.parseFloat(row[2])).filter(Number.isFinite);
    const maximum = Math.max(...composites, 1);
    const scoreboard = document.createElement("section");
    scoreboard.className = "deck-scoreboard";
    scoreboard.setAttribute("aria-label", "Compact official leaderboard");
    const header = document.createElement("div");
    header.className = "deck-score-header";
    ["Rank", "Team", "Composite", "nDCG@20", "Catalog", "Lexical", "LLM /5"].forEach((text) => {
      const label = document.createElement("span");
      label.textContent = text;
      header.append(label);
    });
    scoreboard.append(header);
    rows.forEach((values, index) => {
      const row = document.createElement("article");
      row.className = "deck-score-row";
      row.style.setProperty("--score-color", teamColors[index % teamColors.length]);
      row.setAttribute("aria-label", `${index + 1}. ${values[0]}, composite ${values[2]}`);
      const rank = document.createElement("span");
      rank.className = "deck-score-rank";
      rank.textContent = String(index + 1);
      const team = document.createElement("span");
      team.className = "deck-score-team";
      team.textContent = values[0];
      const composite = document.createElement("span");
      composite.className = "deck-score-value deck-score-composite";
      composite.style.setProperty("--score-width", `${(Number.parseFloat(values[2]) / maximum) * 100}%`);
      composite.textContent = values[2];
      row.append(rank, team, composite);
      values.slice(3, 7).forEach((value) => {
        const metric = document.createElement("span");
        metric.className = "deck-score-value";
        metric.textContent = value;
        row.append(metric);
      });
      scoreboard.append(row);
    });
    leaderboardDetails.before(scoreboard);
  }

  const progressiveSlides = [
    "ours/walkthrough",
    "leaders/volart-response",
    "leaders/niwatori-response",
    "leaders/swyoo-response",
    "leaders/team2-response",
  ];
  progressiveSlides.forEach((slug) => {
    const slideNode = document.getElementById(slug);
    const inner = slideNode?.querySelector(":scope > .deck-slide-inner");
    if (!slideNode || !inner) return;
    const paragraphs = [...slideNode.querySelectorAll("[data-artifact-block-id] .portable-markdown > p")]
      .filter((paragraph) => paragraph.querySelector(":scope > strong:first-child"));
    if (paragraphs.length < 3) return;
    slideNode.classList.add("deck-progressive");
    const grid = document.createElement("section");
    grid.className = "deck-insight-grid";
    grid.setAttribute("aria-label", `${slideNode.querySelector(".deck-slide-heading")?.textContent || "System"} detail cards`);
    paragraphs.forEach((paragraph) => {
      const strong = paragraph.querySelector(":scope > strong:first-child");
      const title = strong.textContent.trim().replace(/[.:]$/, "");
      const remainder = paragraph.textContent.slice(strong.textContent.length).trim();
      const sentence = remainder.match(/^.*?[.!?](?:\s|$)/)?.[0]?.trim() || remainder;
      const card = document.createElement("details");
      card.className = "deck-insight-card";
      const summary = document.createElement("summary");
      const titleNode = document.createElement("span");
      titleNode.className = "deck-insight-title";
      titleNode.textContent = title;
      const lede = document.createElement("span");
      lede.className = "deck-insight-lede";
      lede.textContent = sentence;
      summary.append(titleNode, lede);
      paragraph.classList.add("deck-insight-detail");
      card.append(summary, paragraph);
      grid.append(card);
    });
    const evidenceAnchor = [...inner.children].find((child) => (
      child.matches("[data-artifact-block-id]") || child.querySelector("[data-artifact-block-id]")
    ));
    inner.insertBefore(grid, evidenceAnchor || null);
  });

  document.querySelectorAll("#synthesis\\/matrix tbody td").forEach((cell) => {
    const value = cell.textContent.trim().toLowerCase();
    const variant = value === "yes" ? "yes" : value === "partial" ? "partial" : value === "not documented" ? "missing" : null;
    if (variant) {
      const label = document.createElement("span");
      label.className = "deck-status-label";
      label.textContent = cell.textContent.trim();
      cell.replaceChildren(label);
      cell.classList.add("deck-status", `deck-status--${variant}`);
    }
  });

  const promoteEmbeddedDocument = (frameOrSource) => {
    const frame = typeof frameOrSource === "string" ? null : frameOrSource;
    const srcdoc = frame ? frame.getAttribute("srcdoc") : frameOrSource;
    if (!srcdoc) return null;
    const host = document.createElement("div");
    host.className = "deck-embedded-document";
    host.dataset.fitState = "promoted";
    host.setAttribute("role", "group");
    host.setAttribute("aria-label", frame?.closest("[data-artifact-block-id]")?.dataset.artifactBlockId?.replaceAll("_", " ") || "Embedded report evidence");
    try {
      const parsed = new DOMParser().parseFromString(srcdoc, "text/html");
      const wrapper = document.createElement("div");
      wrapper.className = "deck-embedded-root";
      const parsedBody = parsed.body;
      if (!parsedBody) throw new Error("embedded document has no body");
      const allowedElements = new Set([
        "a", "abbr", "article", "aside", "b", "blockquote", "br", "caption", "cite", "code", "col", "colgroup",
        "dd", "details", "div", "dl", "dt", "em", "figcaption", "figure", "footer", "h1", "h2", "h3", "h4",
        "h5", "h6", "header", "hr", "i", "img", "kbd", "li", "main", "mark", "ol", "p", "pre", "q", "s",
        "section", "small", "span", "strong", "sub", "summary", "sup", "table", "tbody", "td", "tfoot", "th",
        "thead", "time", "tr", "u", "ul",
      ]);
      const allowedAttributes = new Set([
        "alt", "class", "colspan", "datetime", "decoding", "dir", "height", "href", "id", "lang", "loading", "open",
        "rel", "role", "rowspan", "scope", "target", "title", "width",
      ]);
      const safeLink = (value) => {
        const compact = value.replace(/[\u0000-\u0020]+/g, "");
        if (/^(?:https?:|mailto:)/i.test(compact)) return true;
        return /^(?:#|\/|\.\/|\.\.\/)/.test(compact);
      };
      [...parsedBody.querySelectorAll("*")].forEach((node) => {
        const tag = node.localName?.toLowerCase() || "";
        if (!allowedElements.has(tag) || node.namespaceURI !== "http://www.w3.org/1999/xhtml") {
          node.remove();
          return;
        }
        [...node.attributes].forEach((attribute) => {
          const name = attribute.name.toLowerCase();
          const allowed = allowedAttributes.has(name) || name.startsWith("aria-") || name.startsWith("data-");
          if (!allowed || name.startsWith("on") || name === "style") node.removeAttribute(attribute.name);
        });
        if (tag === "img") {
          const source = node.getAttribute("src") || "";
          if (!/^(?:data:image\/(?:avif|gif|jpeg|png|webp);|blob:)/i.test(source)) node.removeAttribute("src");
        }
        if (tag === "a") {
          const href = node.getAttribute("href") || "";
          if (!safeLink(href)) {
            node.replaceWith(...node.childNodes);
            return;
          }
          node.setAttribute("rel", "noreferrer noopener");
          node.setAttribute("target", "_blank");
        }
      });
      wrapper.append(...parsedBody.childNodes);
      if (frame?.closest(".deck-slide--audit")) wrapper.querySelectorAll("details").forEach((details) => { details.open = true; });
      const decodeCssEscapes = (value) => value.replace(/\\([0-9a-f]{1,6})\s?|\\([^\r\n0-9a-f])/gi, (_, hex, escaped) => (
        hex ? String.fromCodePoint(Number.parseInt(hex, 16)) : escaped
      ));
      const sourceCss = [...parsed.querySelectorAll("style")].map((node) => node.textContent || "").filter((css) => {
        const normalized = decodeCssEscapes(css.replace(/\/\*[\s\S]*?\*\//g, "")).toLowerCase();
        return !/@import|url\s*\(|image-set\s*\(|expression\s*\(|(?:^|[;{])\s*behavior\s*:|-moz-binding\s*:|javascript:|vbscript:|data:text\/html|https?:\/\//i.test(normalized);
      }).join("\n");
      const style = document.createElement("style");
      style.textContent = `${sourceCss}\n:host{display:block;min-width:0;color:CanvasText;background:Canvas;font:14px/1.5 system-ui,sans-serif}.deck-embedded-root{min-width:0;overflow:visible}*,*::before,*::after{box-sizing:border-box;max-width:100%}img,svg{height:auto}section,div,article,details{overflow:visible!important}table{width:100%!important;table-layout:fixed!important;border-collapse:collapse}th,td{min-width:0!important;white-space:normal!important;overflow-wrap:anywhere!important;word-break:normal!important;vertical-align:top}pre,code{white-space:pre-wrap;overflow-wrap:anywhere}.state-contract ul{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:10px 0;padding:0;list-style:none}.state-contract li{padding:12px;border:1px solid color-mix(in srgb,CanvasText 18%,Canvas);border-radius:10px;background:color-mix(in srgb,#1687ff 7%,Canvas)}.state-contract li strong{display:block;margin-bottom:4px;color:#0877da}@media(max-width:900px){.state-contract ul{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:700px){table{font-size:12px!important}th,td{padding:7px!important}.state-contract ul{grid-template-columns:1fr}}`;
      const shadow = host.attachShadow({ mode: "open" });
      shadow.append(style, wrapper);
      if (frame) {
        frame.after(host);
        frame.hidden = true;
      }
      return host;
    } catch (error) {
      host.dataset.fitState = "fallback";
      host.hidden = true;
      if (frame) frame.after(host);
      return null;
    }
  };
  app.querySelectorAll(".portable-custom-html iframe[srcdoc]").forEach(promoteEmbeddedDocument);

  const disclosures = () => document.querySelectorAll("details.deck-disclosure,details.deck-insight-card");
  const setAllOpen = (stateKey) => disclosures().forEach((details) => {
    if (!(stateKey in details.dataset)) details.dataset[stateKey] = details.open ? "true" : "false";
    details.open = true;
  });
  const restoreOpen = (stateKey) => disclosures().forEach((details) => {
    if (stateKey in details.dataset) {
      details.open = details.dataset[stateKey] === "true";
      delete details.dataset[stateKey];
    }
  });
  const setCanonicalOrder = (enabled) => {
    const deckOrder = CONFIG.chapters.map(({ slug }) => slug);
    const canonicalOrder = ["outcome", "diagnosis", "query", "retrieval", "response", "ours", "leaders", "synthesis"];
    const order = enabled ? canonicalOrder : deckOrder;
    const chaptersBySlug = new Map([...track.querySelectorAll(":scope > .deck-chapter")].map((node) => [node.dataset.chapter, node]));
    order.forEach((slug) => {
      const chapter = chaptersBySlug.get(slug);
      if (chapter) track.append(chapter);
    });
    const dataKnowledge = document.getElementById("query/data-glossary");
    const dataMatrix = document.getElementById("query/data-matrix");
    const promptAudit = document.getElementById("query/prompt-audit");
    const vertical = dataKnowledge?.parentElement;
    if (!vertical || dataMatrix?.parentElement !== vertical || promptAudit?.parentElement !== vertical) return;
    if (enabled) vertical.insertBefore(promptAudit, dataKnowledge);
    else vertical.insertBefore(promptAudit, dataMatrix.nextSibling);
  };

  const slides = CONFIG.chapters.flatMap((chapter, chapterIndex) => chapter.slides.map((entry, slideIndex) => ({
    chapter,
    entry,
    chapterIndex,
    slideIndex,
    slug: `${chapter.slug}/${entry.slug}`,
  })));
  const bySlug = new Map(slides.map((item) => [item.slug, item]));
  const resolveSlug = (slug) => CONFIG.aliases[slug] || slug;
  const breadcrumb = topbar.querySelector(".deck-breadcrumb");
  const progress = topbar.querySelector(".deck-progress");
  const mobileOrientation = topbar.querySelector(".deck-mobile-orientation");
  let active = slides[0];
  let readingPath = new URL(location.href).searchParams.get("path") === "curated" ? "curated" : "audit";
  let scrollTimer = 0;
  let programmaticTarget = null;
  let gestureOrigin = null;

  const openRequestedDisclosure = () => {
    const params = new URLSearchParams(location.hash.split("?")[1] || "");
    const id = params.get("open");
    if (id) document.querySelector(`details[data-disclosure-for="${CSS.escape(id)}"]`)?.setAttribute("open", "");
  };
  const chapterSlidesFor = (item) => slides.filter((candidate) => candidate.chapterIndex === item.chapterIndex);
  const horizontal = (delta) => {
    const chapterIndex = active.chapterIndex + delta;
    if (chapterIndex < 0 || chapterIndex >= CONFIG.chapters.length) return active;
    return slides.find((item) => item.chapterIndex === chapterIndex && item.slideIndex === 0) || active;
  };
  const verticalItem = (delta) => {
    const chapterSlides = chapterSlidesFor(active);
    return chapterSlides[Math.max(0, Math.min(chapterSlides.length - 1, active.slideIndex + delta))];
  };
  const navigationItems = () => readingPath === "curated"
    ? CONFIG.curatedPath.map((slug) => bySlug.get(slug)).filter(Boolean)
    : slides;
  const updateCurrent = (item, announce = false) => {
    active = item;
    document.querySelectorAll('.deck-slide[aria-current="true"],.deck-rail-button[aria-current="true"],.deck-chapter-button[aria-current="true"]').forEach((node) => node.removeAttribute("aria-current"));
    const target = document.getElementById(item.slug);
    target.setAttribute("aria-current", "true");
    document.querySelector(`.deck-rail-button[data-go="${CSS.escape(item.slug)}"]`)?.setAttribute("aria-current", "true");
    chapterRail.children[item.chapterIndex]?.setAttribute("aria-current", "true");
    breadcrumb.textContent = `${item.chapter.title} / ${item.entry.title}`;
    progress.textContent = `Chapter ${item.chapterIndex + 1}/${CONFIG.chapters.length} · slide ${item.slideIndex + 1}/${CONFIG.chapters[item.chapterIndex].slides.length}`;
    mobileOrientation.textContent = `${item.chapter.title} · ${item.slideIndex + 1}/${CONFIG.chapters[item.chapterIndex].slides.length}`;
    skip.href = `#${item.slug}`;
    const chapterSlides = chapterSlidesFor(item);
    const pathItems = navigationItems();
    const pathIndex = pathItems.indexOf(item);
    const previousItem = readingPath === "curated"
      ? pathItems[pathIndex - 1]
      : item.slideIndex > 0
        ? chapterSlides[item.slideIndex - 1]
        : slides.find((candidate) => candidate.chapterIndex === item.chapterIndex - 1 && candidate.slideIndex === 0);
    const nextItem = readingPath === "curated"
      ? pathItems[pathIndex + 1]
      : item.slideIndex < chapterSlides.length - 1
        ? chapterSlides[item.slideIndex + 1]
        : slides.find((candidate) => candidate.chapterIndex === item.chapterIndex + 1 && candidate.slideIndex === 0);
    const previousButton = footer.querySelector('[data-action="previous"]');
    const nextButton = footer.querySelector('[data-action="next"]');
    previousButton.disabled = !previousItem;
    previousButton.textContent = previousItem ? `← ${previousItem.entry.title}` : "← Start";
    nextButton.disabled = !nextItem;
    nextButton.textContent = nextItem ? `${nextItem.entry.title} →` : "End";
    if (announce) live.textContent = `${item.chapter.title}, ${item.entry.title}`;
  };
  const setReadingPath = (mode) => {
    readingPath = mode === "curated" ? "curated" : "audit";
    html.dataset.readingPath = readingPath;
    const url = new URL(location.href);
    url.searchParams.set("path", readingPath);
    history.replaceState(history.state, "", url.href);
    topbar.querySelector('[data-action="reading-path"]').textContent = readingPath === "curated" ? "Explore evidence audit" : "Read retrospective";
    updateCurrent(active, false);
  };
  const goTo = (slug, { push = true, focus = true, announce = true, behavior = null } = {}) => {
    const requestedSlug = slug.split("?")[0];
    const cleanSlug = resolveSlug(requestedSlug);
    const item = bySlug.get(cleanSlug) || slides[0];
    if (readingPath === "curated" && !CONFIG.curatedPath.includes(item.slug)) setReadingPath("audit");
    const target = document.getElementById(item.slug);
    const scrollBehavior = behavior || (matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth");
    programmaticTarget = scrollBehavior === "smooth" ? item.slug : null;
    gestureOrigin = null;
    const scrollContainers = [track, target.closest(".deck-vertical")];
    const previousInlineBehavior = scrollContainers.map((node) => node.style.scrollBehavior);
    if (scrollBehavior === "auto") scrollContainers.forEach((node) => { node.style.scrollBehavior = "auto"; });
    target.scrollIntoView({ behavior: scrollBehavior, block: "start", inline: "start" });
    if (scrollBehavior === "auto") scrollContainers.forEach((node, index) => { node.style.scrollBehavior = previousInlineBehavior[index]; });
    updateCurrent(item, announce);
    const nextHash = `#${item.slug}${slug.includes("?") ? `?${slug.split("?")[1]}` : ""}`;
    if (push) history.pushState({ slug: item.slug }, "", nextHash);
    else history.replaceState({ slug: item.slug }, "", nextHash);
    openRequestedDisclosure();
    if (focus) target.focus({ preventScroll: true });
    return item;
  };
  const setLinear = (enabled) => {
    if (enabled) setAllOpen("deckLinearOpen"); else restoreOpen("deckLinearOpen");
    setCanonicalOrder(enabled);
    html.dataset.deckView = enabled ? "linear" : "deck";
    const url = new URL(location.href);
    if (enabled) url.searchParams.set("view", "linear"); else url.searchParams.delete("view");
    history.replaceState(history.state, "", url.href);
    topbar.querySelector('[data-action="linear"]').textContent = enabled ? "Deck view" : "Linear view";
  };
  const nearest = (nodes, axis) => [...nodes].reduce((best, node) => (
    Math.abs(node.getBoundingClientRect()[axis]) < Math.abs(best.getBoundingClientRect()[axis]) ? node : best
  ));
  const syncFromScroll = () => {
    if (html.dataset.deckView === "linear") return;
    const chapterNode = nearest(track.querySelectorAll(".deck-chapter"), "left");
    const slideNode = nearest(chapterNode.querySelectorAll(".deck-slide"), "top");
    const item = bySlug.get(slideNode.dataset.slug);
    if (!item) return;
    if (readingPath === "curated" && !CONFIG.curatedPath.includes(item.slug)) setReadingPath("audit");
    if (programmaticTarget) {
      const reachedTarget = item.slug === programmaticTarget;
      programmaticTarget = null;
      if (!reachedTarget) {
        updateCurrent(item, false);
        history.replaceState({ slug: item.slug }, "", `#${item.slug}`);
      }
      return;
    }
    if (item.slug !== active.slug) updateCurrent(item, false);
    if (gestureOrigin) {
      if (item.slug !== gestureOrigin) {
        history.replaceState({ slug: gestureOrigin }, "", `#${gestureOrigin}`);
        history.pushState({ slug: item.slug }, "", `#${item.slug}`);
      }
      gestureOrigin = null;
    }
  };
  const noteScroll = () => {
    if (!programmaticTarget && !gestureOrigin) gestureOrigin = active.slug;
    clearTimeout(scrollTimer);
    scrollTimer = setTimeout(syncFromScroll, 80);
  };
  track.addEventListener("scroll", noteScroll, { passive: true });
  track.querySelectorAll(".deck-vertical").forEach((node) => node.addEventListener("scroll", noteScroll, { passive: true }));

  const jump = document.createElement("div");
  jump.className = "deck-jump";
  jump.dataset.open = "false";
  jump.setAttribute("role", "dialog");
  jump.setAttribute("aria-modal", "true");
  jump.setAttribute("aria-label", "Jump anywhere");
  jump.innerHTML = '<div class="deck-jump-panel"><label>Search chapters, teams, or topics<input class="deck-jump-input" type="search" role="searchbox"></label><div class="deck-jump-list"></div></div>';
  app.append(jump);
  const input = jump.querySelector(".deck-jump-input");
  const list = jump.querySelector(".deck-jump-list");
  let jumpOpener = null;
  const searchText = (item) => {
    const slideNode = document.getElementById(item.slug);
    const iframeText = [...slideNode.querySelectorAll("iframe")].map((frame) => frame.getAttribute("srcdoc") || "").join(" ");
    return `${item.chapter.title} ${item.entry.title} ${item.slug} ${slideNode.textContent} ${iframeText}`.toLowerCase();
  };
  const renderJump = (query = "") => {
    list.replaceChildren();
    const normalized = query.trim().toLowerCase();
    for (const item of slides.filter((candidate) => searchText(candidate).includes(normalized))) {
      const button = document.createElement("button");
      button.className = "deck-jump-item";
      button.type = "button";
      button.textContent = `${item.chapter.title} — ${item.entry.title}`;
      button.addEventListener("click", () => {
        closeJump(false);
        goTo(item.slug);
      });
      list.append(button);
    }
  };
  const setBackgroundInert = (inert) => [topbar, track, footer].forEach((node) => { node.inert = inert; });
  const openJump = (opener = document.activeElement) => {
    jumpOpener = opener instanceof HTMLElement ? opener : topbar.querySelector('[data-action="jump"]');
    jump.dataset.open = "true";
    setBackgroundInert(true);
    renderJump();
    input.value = "";
    input.focus();
  };
  const closeJump = (restore = true) => {
    jump.dataset.open = "false";
    setBackgroundInert(false);
    if (restore) jumpOpener?.focus();
  };
  input.addEventListener("input", () => renderJump(input.value));
  const interactive = (target) => target instanceof Element && target.closest("input,textarea,select,button,a,summary,details,[contenteditable=true],iframe,.portable-table-scroll");
  app.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    const destination = target?.closest("[data-go]")?.dataset.go;
    if (destination) {
      goTo(destination);
      return;
    }
    const action = target?.closest("[data-action]")?.dataset.action;
    if (action === "jump") openJump(target);
    if (action === "reading-path") setReadingPath(readingPath === "curated" ? "audit" : "curated");
    if (action === "linear") setLinear(html.dataset.deckView !== "linear");
    if (action === "previous") {
      const pathItems = navigationItems();
      const destination = readingPath === "curated" ? pathItems[pathItems.indexOf(active) - 1] : active.slideIndex ? verticalItem(-1) : horizontal(-1);
      if (destination) goTo(destination.slug);
    }
    if (action === "next") {
      const pathItems = navigationItems();
      const chapterSlides = chapterSlidesFor(active);
      const destination = readingPath === "curated" ? pathItems[pathItems.indexOf(active) + 1] : active.slideIndex < chapterSlides.length - 1 ? verticalItem(1) : horizontal(1);
      if (destination) goTo(destination.slug);
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && jump.dataset.open === "true") {
      event.preventDefault();
      closeJump();
      return;
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      jump.dataset.open === "true" ? closeJump() : openJump();
      return;
    }
    if (!event.ctrlKey && !event.metaKey && event.key.toLowerCase() === "j" && !interactive(event.target)) {
      event.preventDefault();
      openJump();
      return;
    }
    if (jump.dataset.open === "true" || interactive(event.target) || html.dataset.deckView === "linear") return;
    const destinations = {
      ArrowLeft: horizontal(-1),
      ArrowRight: horizontal(1),
      ArrowUp: verticalItem(-1),
      ArrowDown: verticalItem(1),
    };
    if (destinations[event.key]) {
      event.preventDefault();
      goTo(destinations[event.key].slug);
    }
  });
  addEventListener("popstate", () => {
    setReadingPath(new URL(location.href).searchParams.get("path"));
    goTo(location.hash.slice(1) || slides[0].slug, { push: false, focus: false, announce: true, behavior: "auto" });
  });
  addEventListener("beforeprint", () => {
    setAllOpen("deckPrintOpen");
    setCanonicalOrder(true);
  });
  addEventListener("afterprint", () => {
    restoreOpen("deckPrintOpen");
    if (html.dataset.deckView !== "linear") setCanonicalOrder(false);
  });
  setReadingPath(readingPath);
  const initial = location.hash.slice(1);
  const initialSlug = resolveSlug(initial.split("?")[0]);
  if (!bySlug.has(initialSlug)) goTo(slides[0].slug, { push: false, focus: false, announce: false, behavior: "auto" });
  else goTo(initial, { push: false, focus: false, announce: false, behavior: "auto" });
  setLinear(new URL(location.href).searchParams.get("view") === "linear");
  html.classList.add("retrospective-deck-ready");
  html.dataset.deckReady = "true";
  window.__retrospectiveDeck = { CONFIG, app, track, live, goTo, setLinear, setReadingPath, promoteEmbeddedDocument, currentReadingPath: () => readingPath, currentSlug: () => active.slug };
}

export const DECK_RUNTIME = `(${runtimeMain.toString()})(__CONFIG__);`;

export function enhanceHtml(input) {
  const html = stripDeckInjection(input);
  validateChapterMap(CHAPTERS, html);
  const config = JSON.stringify({ chapters: CHAPTERS, curatedPath: CURATED_PATH, disclosures: DISCLOSURES, aliases: Object.fromEntries(LEGACY_ALIASES) }).replaceAll("<", "\\u003c");
  const style = `${STYLE_START}\n<style data-retrospective-deck-style>${DECK_STYLE}</style>\n${STYLE_END}`;
  const runtime = DECK_RUNTIME.replace("__CONFIG__", config);
  const script = `${SCRIPT_START}\n<script data-retrospective-deck-script>${runtime}</script>\n${SCRIPT_END}`;
  if (!html.includes("</head>") || !html.includes("</body>")) throw new Error("portable report is missing head/body terminators");
  return html.replace("</head>", `${style}\n</head>`).replace("</body>", `${script}\n</body>`);
}

function parseArgs(argv) {
  const args = { input: "", output: "", check: "" };
  for (let index = 0; index < argv.length; index += 1) {
    const key = argv[index];
    if (key === "--input" || key === "--output" || key === "--check") args[key.slice(2)] = argv[++index] ?? "";
    else throw new Error(`unknown argument: ${key}`);
  }
  if (args.check) return args;
  if (!args.input || !args.output) throw new Error("usage: retrospective_deck.mjs --input PATH --output PATH | --check PATH");
  return args;
}

async function main(argv) {
  const args = parseArgs(argv);
  const inputPath = args.check || args.input;
  const source = await readFile(inputPath, "utf8");
  const enhanced = enhanceHtml(source);
  if (args.check) {
    process.stdout.write(`PASS: ${validateChapterMap(CHAPTERS, stripDeckInjection(source)).reportIds.length} blocks mapped into ${CHAPTERS.length} chapters\n`);
    return;
  }
  const temp = `${args.output}.tmp-${process.pid}`;
  await writeFile(temp, enhanced, "utf8");
  await rename(temp, args.output);
  process.stdout.write(`wrote ${args.output}\n`);
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  main(process.argv.slice(2)).catch((error) => {
    process.stderr.write(`${error.message}\n`);
    process.exitCode = 1;
  });
}
