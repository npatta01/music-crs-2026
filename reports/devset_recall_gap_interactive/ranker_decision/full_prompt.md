Build a decision-ready Music CRS devset recall-gap report for v0plus_compiler_all_retrievers_devset.

Sources to inspect:
- exp/inference/devset/v0plus_compiler_all_retrievers_devset_trace.jsonl
- exp/inference/devset/v0plus_compiler_all_retrievers_devset.json
- evaluator/exp/ground_truth/devset.json
- reports/devset_recall_gap_interactive/recall_gap_data.json
- reports/devset_recall_gap_interactive/branch_diagnostics.json
- configs/v0plus_compiler_all_retrievers_devset.yaml
- docs/data.md, docs/architectures/session_state.md, docs/architectures/v0plus_retrieval.md
- Hugging Face TalkPlayData-Challenge-Dataset test split for raw conversation turns
- Hugging Face organizer metadata: conversation_goal.category/specificity/listener_goal, goal_progress_assessments, user_profile.preferred_musical_culture
- Hugging Face Blind-A schema check to determine whether organizer metadata is usable at inference time
- Local or Modal LanceDB catalog when schema/ranker feature fields are needed

Central questions:
1. Treat union@20 as the first decision boundary. If gold is not in union@20, classify it as a candidate-generation/state/retriever gap. If gold is in union@20 but not final top-20, classify it as fusion, ranker, post-fusion, or finalization loss.
2. Also report union@100 and union@1000 so we can separate near misses from deep retriever misses.
3. Diagnose whether misses come from state being wrong or incomplete. Compare raw user turns and recent conversation against trace.state.turn_intent, mentioned_entities, release_year_range, routing_tags, resolver anchors, and exploration_policy.
4. Check whether fields in the data are not being used enough: conversation_goal, user_profile, profile culture, track popularity, tags, duration, artist/album IDs, track/user embeddings, and LanceDB vector fields.
5. Decide whether the next step should be better state, better use of state, better retrievers, post-fusion fixes, or replacing the current fusion stage with a trained ranker.
6. Include concrete examples of gaps or bugs. Each example should show session_id, turn_number, raw user turn, recent context, ground-truth track/artist, final/fused/branch ranks, state fields, branch ranks, post-fusion symptoms, classification, and the smallest fix or experiment.
7. Separate confirmed bugs/config gaps from plausible gaps. Do not call something a bug unless the code/config/artifact proves it.

Output:
- Primary: visually clear HTML report with charts and an example explorer.
- Companion: Markdown report for future agents.
- Include the full prompt and source/caveat notes.
